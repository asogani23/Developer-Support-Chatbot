import os
import time
import sqlite3
import pandas as pd
import streamlit as st
from contextlib import closing

DB_PATH = os.environ.get("CHATBOT_DB", "logs.db")
API_URL = os.environ.get("CHATBOT_API", "http://127.0.0.1:5000/query")

st.set_page_config(page_title="Dev Support Chatbot • Dashboard", layout="wide")

@st.cache_resource
def get_conn():
    # Single connection per session; safe because we only read or do small writes
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            query TEXT NOT NULL,
            response TEXT NOT NULL,
            latency_ms INTEGER NOT NULL
        );
    """)
    conn.commit()

conn = get_conn()
init_db(conn)

st.title("🛠️ Dev Support Chatbot — Live Dashboard")

with st.expander("Send a test query"):
    q = st.text_input("Query", placeholder="e.g., How do I fix a Python KeyError?")
    col_a, col_b = st.columns([1,1])
    with col_a:
        run_btn = st.button("Send", type="primary", use_container_width=True)
    with col_b:
        refresh_btn = st.button("Refresh data", use_container_width=True)

    if run_btn and q.strip():
        import requests, datetime as dt
        try:
            r = requests.post(API_URL, json={"query": q.strip()}, timeout=20)
            if r.ok:
                payload = r.json()
                st.success(f"Response ({payload.get('latency_ms')} ms @ {payload.get('timestamp')}):")
                st.code(payload.get("response", "")[:1000])  # keep short on screen
            else:
                st.error(f"API error {r.status_code}: {r.text[:300]}")
        except Exception as e:
            st.error(f"Request failed: {e}")

# --- Load data from DB
df = pd.read_sql_query("SELECT * FROM interactions ORDER BY id DESC", conn)

st.subheader("📒 Query Log")
if df.empty:
    st.info("No queries yet. Send one above to populate the log.")
else:
    # Pretty columns
    df_pretty = df.rename(columns={
        "ts": "Timestamp",
        "query": "Query",
        "response": "Response",
        "latency_ms": "Latency (ms)",
    })
    # Avoid huge cells
    df_pretty["Response"] = df_pretty["Response"].str.slice(0, 300)
    st.dataframe(df_pretty.drop(columns=["id"]), use_container_width=True, height=300)

st.markdown("---")
st.subheader("📈 Analytics")

if df.empty:
    st.info("No data to display yet.")
    st.stop()

# Ensure proper dtypes
df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
df = df.dropna(subset=["ts"])

# KPI row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Queries (all time)", len(df))
with col2:
    st.metric("Unique Questions", df["query"].nunique())
with col3:
    st.metric("Avg Latency (ms)", round(df["latency_ms"].mean(), 1))
with col4:
    st.metric("P95 Latency (ms)", int(df["latency_ms"].quantile(0.95)) if len(df) >= 2 else int(df["latency_ms"].max()))

# Queries over time (per minute bucket, accumulative)
df_time = (
    df.assign(bucket=df["ts"].dt.floor("min"))
      .groupby("bucket").size().sort_index().rename("count").reset_index()
)
df_time["cumulative"] = df_time["count"].cumsum()

st.write("**Queries per minute (bar)**")
st.bar_chart(df_time.set_index("bucket")["count"])

st.write("**Cumulative queries (line)**")
st.line_chart(df_time.set_index("bucket")["cumulative"])

# Top repeated questions
st.write("**Top repeated queries**")
top_queries = (
    df.groupby("query").size().sort_values(ascending=False).head(10).rename("Count").reset_index()
)
st.dataframe(top_queries, use_container_width=True)

# Latency distribution
st.write("**Latency distribution (ms)**")
st.bar_chart(df["latency_ms"])

st.caption("Data persisted in SQLite — charts now reflect true totals across sessions, not just current run.")
