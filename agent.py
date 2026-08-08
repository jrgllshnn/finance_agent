"""
News Agent — fetches finance/crypto news, judges each item, stores the good ones.

The "agent" part is the judge step: for each item the LLM decides
significance + whether it looks like hype/shilling, and tags it. That
judgment is what makes this more than a dumb fetch-and-dump pipeline.

Run it:  python agent.py
By default it uses a MOCK judge so you can run it with zero setup.
Set USE_GEMINI = True and add your key to switch to a real LLM.
"""

import feedparser
import sqlite3
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
USE_GEMINI = True  
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_GEMINI_CLIENT = None  
DB_PATH = "news.db" # the output path

# contains only free RSS feeds
FEEDS = {
    "Yahoo Finance":        "https://finance.yahoo.com/news/rssindex",
    "MarketWatch Top":      "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch Realtime": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "CNBC Top News":        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CoinDesk":             "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph":        "https://cointelegraph.com/rss",
    "Investing.com":        "https://www.investing.com/rss/news.rss",
}

# ---------------------------------------------------------------------------
# 1. FETCH — pull recent items from each feed
# ---------------------------------------------------------------------------
_FEED_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (news-agent)"

def fetch_items(max_per_feed=10):
    items = []
    for source, url in FEEDS.items():
        feed = feedparser.parse(url, agent=_FEED_USER_AGENT)
        if not feed.entries:
            print(f"  ⚠ {source}: 0 items (feed may be dead or blocked)")
        for entry in feed.entries[:max_per_feed]:
            items.append({
                "source": source,
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "").strip()[:400],
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
    return items

# ---------------------------------------------------------------------------
# 2. JUDGE — This is the agentic heart. It decides the significance and hype for each item. This function is the only thing that talks to an LLM, so swapping 
# between LLMs later means only editing here
# ---------------------------------------------------------------------------
JUDGE_INSTRUCTIONS = """You are a skeptical financial news editor. For the news item given, return a JSON object with exactly these fields:
- "significance": integer 1-5 (5 = major market-moving event, 1 = noise/filler)
- "hype": true/false (true if it reads like promotion, shilling, or a pump piece rather than reporting)
- "category": one of "macro", "crypto", "equities", "forex", "other"
- "one_line": a neutral one-sentence summary in plain English

Return ONLY the JSON object, no other text."""

def judge_mock(item):
    """A stand-in judge so the pipeline runs with zero setup.
    Uses trivial rules just so you can see the whole loop work."""
    text = (item["title"] + " " + item["summary"]).lower()
    hype_words = ["moon", "1000x", "guaranteed", "explode", "don't miss", "skyrocket"]
    hype = any(w in text for w in hype_words)
    if any(w in text for w in ["fed", "rate", "inflation", "ecb"]):
        category = "macro"
    elif any(w in text for w in ["bitcoin", "crypto", "ethereum", "token"]):
        category = "crypto"
    else:
        category = "other"
    return {
        "significance": 2,
        "hype": hype,
        "category": category,
        "one_line": item["title"],
    }

_LAST_GEMINI_CALL = 0.0
_GEMINI_MIN_INTERVAL = 2.5  # seconds; stays under the free tier's ~5 requests/minute cap

def judge_gemini(item):
    """Real judge using Google's free Gemini API (new google-genai SDK)."""
    global _LAST_GEMINI_CALL, _GEMINI_CLIENT
    from google import genai
    from google.genai import types, errors

    # Reuse one client across calls instead of rebuilding it each time
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"{JUDGE_INSTRUCTIONS}\n\nITEM:\nTitle: {item['title']}\nSummary: {item['summary']}"

    for attempt in range(5):
        wait = _GEMINI_MIN_INTERVAL - (time.time() - _LAST_GEMINI_CALL)
        if wait > 0:
            time.sleep(wait)
        _LAST_GEMINI_CALL = time.time()
        try:
            resp = _GEMINI_CLIENT.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            raw = json.loads(resp.text)
            # Normalize so bad/missing fields can't crash the pipeline
            return {
                "significance": int(raw.get("significance", 1)),
                "hype": bool(raw.get("hype", False)),
                "category": raw.get("category", "other"),
                "one_line": raw.get("one_line", item["title"]),
            }
        except errors.APIError as e:
            if getattr(e, "code", None) == 429:
                time.sleep(20)   # free-tier quota hit, back off further
                continue
            raise            # auth/400/etc. — fail fast, don't silently retry
        except (json.JSONDecodeError, ValueError, TypeError):
            continue         # model glitched on this response, retry

    raise RuntimeError("Gemini judge failed after retries (quota or bad output)")

def judge(item):
    return judge_gemini(item) if USE_GEMINI else judge_mock(item)


# ---------------------------------------------------------------------------
# 3. STORE — write judged items to SQLite (this is the "organize" + archive)
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            link TEXT PRIMARY KEY,
            source TEXT, title TEXT, one_line TEXT,
            significance INTEGER, hype INTEGER, category TEXT,
            published TEXT, fetched_at TEXT
        )
    """)
    conn.commit()
    return conn

def store(conn, item, verdict):
    conn.execute("""
        INSERT OR IGNORE INTO items
        (link, source, title, one_line, significance, hype, category, published, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item["link"], item["source"], item["title"], verdict["one_line"],
        verdict["significance"], int(verdict["hype"]), verdict["category"],
        item["published"], datetime.now().isoformat(),
    ))


# ---------------------------------------------------------------------------
# MAIN — fetch, judge each, store, print a quick digest
# ---------------------------------------------------------------------------
def run():
    conn = init_db()
    items = fetch_items()
    print(f"Fetched {len(items)} items. Judging...\n")

    kept = []
    for item in items:
        if not item["title"]:
            continue
        verdict = judge(item)
        store(conn, item, verdict)
        if not verdict["hype"] and verdict["significance"] >= 2:
            kept.append((item, verdict))
    conn.commit()

    # Simple text digest, sorted by significance
    kept.sort(key=lambda x: x[1]["significance"], reverse=True)
    print("=== TODAY'S DIGEST ===")
    for item, v in kept:
        print(f"[{v['significance']}] ({v['category']}) {v['one_line']}")
        print(f"      {item['source']} — {item['link']}\n")
    print(f"Stored {len(items)} items total in {DB_PATH}.")

if __name__ == "__main__":
    run()
