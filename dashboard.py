"""
Dashboard — a browser UI over the news the agent collected.

Run it:  streamlit run dashboard.py
Then open the URL it prints (usually http://localhost:8501).

This just READS news.db. The agent (agent.py) writes to it.
Keeping them separate is deliberate: the agent does the thinking,
the dashboard only displays. You can run either one independently.
"""

import streamlit as st
import sqlite3
import pandas as pd

DB_PATH = "news.db"

st.set_page_config(page_title="News Agent", layout="wide")
st.title("📈 Finance & Crypto News Agent")

@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT significance, category, one_line, source, title, link, hype, published "
        "FROM items ORDER BY significance DESC, fetched_at DESC",
        conn,
    )
    conn.close()
    return df

try:
    df = load_data()
except Exception:
    st.warning("No database yet. Run `python agent.py` first to collect news.")
    st.stop()

if df.empty:
    st.info("Database is empty. Run `python agent.py` to fetch and judge news.")
    st.stop()

# --- Sidebar filters ---
st.sidebar.header("Filters")
hide_hype = st.sidebar.checkbox("Hide hype / shilling", value=True)
min_sig = st.sidebar.slider("Minimum significance", 1, 5, 2)
cats = st.sidebar.multiselect(
    "Categories",
    options=sorted(df["category"].unique()),
    default=sorted(df["category"].unique()),
)
search = st.sidebar.text_input("Search text")

# --- Apply filters ---
view = df.copy()
if hide_hype:
    view = view[view["hype"] == 0]
view = view[view["significance"] >= min_sig]
view = view[view["category"].isin(cats)]
if search:
    mask = view["title"].str.contains(search, case=False, na=False) | \
           view["one_line"].str.contains(search, case=False, na=False)
    view = view[mask]

st.caption(f"Showing {len(view)} of {len(df)} stored items")

# --- Render each item as a card ---
for _, row in view.iterrows():
    stars = "⭐" * int(row["significance"])
    st.markdown(f"**{stars} · {row['category'].upper()}** — {row['source']}")
    st.markdown(f"### [{row['title']}]({row['link']})")
    if row["one_line"] and row["one_line"] != row["title"]:
        st.write(row["one_line"])
    st.divider()
