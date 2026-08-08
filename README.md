# News Agent

A small AI agent that fetches finance/crypto/investing news, judges each item
(significance + hype detection + category), stores the results, and shows them
in a browser dashboard.

## What makes it an "agent" (not just a feed reader)
The **judge** step: for every news item, the LLM decides how significant it is,
whether it's real reporting or hype/shilling, and how to categorize it. That
per-item judgment — and filtering the noise out — is the point.

## Files
- `agent.py` — fetches, judges, stores. This is the brain. Run it to collect news.
- `dashboard.py` — Streamlit UI that displays what the agent collected.
- `news.db` — SQLite database (created automatically). Your growing news archive.

## Setup (free)

1. Install dependencies:
   ```
   pip install feedparser streamlit pandas google-generativeai
   ```

2. Run the agent (works immediately with the built-in MOCK judge — no key needed):
   ```
   python agent.py
   ```

3. See it in the browser:
   ```
   streamlit run dashboard.py
   ```

## Switching to a real LLM (Google Gemini — free tier)

1. Get a free API key at https://aistudio.google.com/apikey
2. Set it as an environment variable:
   ```
   export GEMINI_API_KEY="your-key-here"      # Windows: set GEMINI_API_KEY=...
   ```
3. In `agent.py`, change `USE_GEMINI = False` to `USE_GEMINI = True`.
4. Run `python agent.py` again — now a real model judges each item.

The mock judge uses crude keyword rules and gives every item significance=2.
The real Gemini judge gives proper 1–5 scores and much smarter hype detection.

## Next steps (build these when you feel the need, not before)
1. **Better sources** — edit the `FEEDS` dict in agent.py. Source quality matters most.
2. **Scheduling** — once it works reliably, run it automatically twice a day via
   cron (Mac/Linux), Task Scheduler (Windows), or free GitHub Actions.
3. **Alerts** — send yourself a notification when an item scores significance 5.
4. **Smarter search** — swap keyword search for embeddings once you have lots of items.
