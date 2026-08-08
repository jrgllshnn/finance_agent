"""
publish.py — turn the news the agent collected into one self-contained web page.

Reads news.db, writes index.html. The page has all its data baked in and does
filtering/search in the browser, so it needs NO server — you can open the file
locally OR publish it to GitHub Pages as-is.

Run it:  python publish.py
Then open index.html in a browser (or let GitHub Actions publish it).
"""

import sqlite3
import json
import html
from datetime import datetime

DB_PATH = "news.db"
OUT_PATH = "index.html"


def load_items():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT significance, category, one_line, source, title, link, hype, published "
        "FROM items ORDER BY significance DESC, fetched_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_html(items):
    total = len(items)
    hype_count = sum(1 for i in items if i["hype"])
    signal_count = total - hype_count
    updated = datetime.now().strftime("%d %b %Y · %H:%M")
    data_json = json.dumps(items)

    # Everything is one file: fonts from CDN, CSS + JS inline, data embedded.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Signal Desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper: #F2F4F6;
    --surface: #FFFFFF;
    --ink: #14202B;
    --muted: #5A6B78;
    --hair: #DDE3E8;
    --control: #12666A;      /* teal = you can act on this */
    --control-soft: #E3EEEE;
    --signal: #C77E12;       /* amber = the agent flags this as significant */
    --signal-soft: #F6ECD9;
    --dim: #9AA7B0;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0; background: var(--paper); color: var(--ink);
    font-family: "IBM Plex Sans", system-ui, sans-serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }}
  .mono {{ font-family: "IBM Plex Mono", monospace; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 0 20px; }}

  header {{ border-bottom: 1.5px solid var(--ink); padding: 40px 0 18px; }}
  .masthead {{ display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  h1 {{
    font-size: 30px; font-weight: 700; letter-spacing: -0.02em; margin: 0;
  }}
  h1 .tick {{ color: var(--signal); }}
  .updated {{ font-family: "IBM Plex Mono", monospace; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
  .stats {{ display: flex; gap: 22px; margin-top: 14px; font-family: "IBM Plex Mono", monospace; font-size: 12.5px; color: var(--muted); }}
  .stats b {{ color: var(--ink); font-weight: 600; }}

  /* filter bar */
  .controls {{ position: sticky; top: 0; background: var(--paper); padding: 16px 0 14px; border-bottom: 1px solid var(--hair); z-index: 5; }}
  .row {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
  .row + .row {{ margin-top: 10px; }}
  .chip {{
    font-family: "IBM Plex Mono", monospace; font-size: 12px; letter-spacing: 0.03em;
    padding: 5px 11px; border: 1px solid var(--hair); background: var(--surface);
    color: var(--muted); border-radius: 2px; cursor: pointer; text-transform: uppercase;
    transition: all .12s ease;
  }}
  .chip:hover {{ border-color: var(--control); color: var(--control); }}
  .chip[aria-pressed="true"] {{ background: var(--control); border-color: var(--control); color: #fff; }}
  .search {{
    flex: 1; min-width: 160px; font-family: "IBM Plex Mono", monospace; font-size: 13px;
    padding: 6px 10px; border: 1px solid var(--hair); border-radius: 2px; background: var(--surface); color: var(--ink);
  }}
  .search:focus, .chip:focus-visible, .toggle:focus-visible {{ outline: 2px solid var(--control); outline-offset: 1px; }}
  .sigctl {{ display: flex; align-items: center; gap: 9px; font-family: "IBM Plex Mono", monospace; font-size: 12px; color: var(--muted); }}
  .sigctl input {{ accent-color: var(--control); }}
  .toggle {{
    font-family: "IBM Plex Mono", monospace; font-size: 12px; letter-spacing: 0.03em;
    padding: 5px 11px; border: 1px solid var(--hair); background: var(--surface); color: var(--muted);
    border-radius: 2px; cursor: pointer; text-transform: uppercase;
  }}
  .toggle[aria-pressed="true"] {{ background: var(--ink); border-color: var(--ink); color: #fff; }}

  /* item */
  .item {{
    display: grid; grid-template-columns: 34px 1fr; gap: 16px;
    padding: 20px 0; border-bottom: 1px solid var(--hair);
  }}
  .item.high {{ margin: 0 -20px; padding: 20px; background: var(--surface); border-bottom: 1px solid var(--hair); box-shadow: inset 3px 0 0 var(--signal); }}
  /* significance gauge — the signature: a signal-strength stack */
  .gauge {{ display: flex; flex-direction: column-reverse; gap: 3px; padding-top: 4px; }}
  .seg {{ height: 7px; border-radius: 1px; background: #E4E9ED; }}
  .seg.on {{ background: var(--control); }}
  .seg.on.hot {{ background: var(--signal); }}
  .signum {{ font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--dim); text-align: center; margin-top: 5px; }}

  .meta {{ font-family: "IBM Plex Mono", monospace; font-size: 11.5px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); margin-bottom: 5px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
  .cat {{ color: var(--control); font-weight: 600; }}
  .cat.hot {{ color: var(--signal); }}
  .headline {{ font-size: 17px; font-weight: 600; line-height: 1.35; margin: 0 0 4px; }}
  .headline a {{ color: var(--ink); text-decoration: none; }}
  .headline a:hover {{ color: var(--control); text-decoration: underline; text-underline-offset: 2px; }}
  .oneline {{ color: var(--muted); font-size: 14px; margin: 0; }}

  .empty {{ text-align: center; padding: 70px 20px; color: var(--muted); font-family: "IBM Plex Mono", monospace; }}
  footer {{ padding: 30px 0 50px; color: var(--dim); font-family: "IBM Plex Mono", monospace; font-size: 11.5px; text-align: center; letter-spacing: 0.04em; }}

  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; scroll-behavior: auto; }} }}
  @media (max-width: 560px) {{ h1 {{ font-size: 24px; }} .item {{ grid-template-columns: 28px 1fr; gap: 12px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="masthead">
      <h1>Signal Desk<span class="tick">.</span></h1>
      <span class="updated">Updated {updated}</span>
    </div>
    <div class="stats">
      <span><b>{signal_count}</b> signal</span>
      <span><b>{hype_count}</b> filtered as hype</span>
      <span><b>{total}</b> total scanned</span>
    </div>
  </header>

  <div class="controls">
    <div class="row" id="cats"></div>
    <div class="row">
      <input class="search" id="search" type="search" placeholder="search headlines…" aria-label="Search headlines">
      <label class="sigctl">min sig
        <input type="range" id="minsig" min="1" max="5" value="1" aria-label="Minimum significance">
        <span class="mono" id="minsigval">1</span>
      </label>
      <button class="toggle" id="hypebtn" aria-pressed="true">hype hidden</button>
    </div>
  </div>

  <main id="list"></main>
  <footer>Generated by a local news agent · filtering runs in your browser</footer>
</div>

<script id="data" type="application/json">{data_json}</script>
<script>
  const ITEMS = JSON.parse(document.getElementById('data').textContent);
  const cats = [...new Set(ITEMS.map(i => i.category))].sort();
  const state = {{ cats: new Set(cats), search: '', minsig: 1, hideHype: true }};

  const catRow = document.getElementById('cats');
  cats.forEach(c => {{
    const b = document.createElement('button');
    b.className = 'chip'; b.textContent = c; b.setAttribute('aria-pressed', 'true');
    b.onclick = () => {{
      if (state.cats.has(c)) {{ state.cats.delete(c); b.setAttribute('aria-pressed','false'); }}
      else {{ state.cats.add(c); b.setAttribute('aria-pressed','true'); }}
      render();
    }};
    catRow.appendChild(b);
  }});

  const esc = s => (s||'').replace(/[&<>"]/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[m]));

  function gauge(sig) {{
    let segs = '';
    for (let n = 1; n <= 5; n++) {{
      const on = n <= sig ? 'on' : '';
      const hot = (n <= sig && sig >= 4) ? 'hot' : '';
      segs += `<div class="seg ${{on}} ${{hot}}"></div>`;
    }}
    return `<div><div class="gauge">${{segs}}</div><div class="signum">${{sig}}</div></div>`;
  }}

  function render() {{
    const q = state.search.toLowerCase();
    const rows = ITEMS.filter(i =>
      state.cats.has(i.category) &&
      i.significance >= state.minsig &&
      (!state.hideHype || !i.hype) &&
      (!q || (i.title + ' ' + (i.one_line||'')).toLowerCase().includes(q))
    );
    const list = document.getElementById('list');
    if (!rows.length) {{ list.innerHTML = '<div class="empty">No items match these filters. Loosen them to see more.</div>'; return; }}
    list.innerHTML = rows.map(i => {{
      const hot = i.significance >= 4;
      return `<article class="item ${{hot?'high':''}}">
        ${{gauge(i.significance)}}
        <div>
          <div class="meta"><span class="cat ${{hot?'hot':''}}">${{esc(i.category)}}</span><span>${{esc(i.source)}}</span></div>
          <h2 class="headline"><a href="${{esc(i.link)}}" target="_blank" rel="noopener">${{esc(i.title)}}</a></h2>
          ${{i.one_line && i.one_line !== i.title ? `<p class="oneline">${{esc(i.one_line)}}</p>` : ''}}
        </div>
      </article>`;
    }}).join('');
  }}

  document.getElementById('search').oninput = e => {{ state.search = e.target.value; render(); }};
  const slider = document.getElementById('minsig');
  slider.oninput = e => {{ state.minsig = +e.target.value; document.getElementById('minsigval').textContent = e.target.value; render(); }};
  const hb = document.getElementById('hypebtn');
  hb.onclick = () => {{ state.hideHype = !state.hideHype; hb.setAttribute('aria-pressed', state.hideHype); hb.textContent = state.hideHype ? 'hype hidden' : 'hype shown'; render(); }};

  render();
</script>
</body>
</html>"""


def main():
    items = load_items()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(build_html(items))
    print(f"Wrote {OUT_PATH} with {len(items)} items.")


if __name__ == "__main__":
    main()