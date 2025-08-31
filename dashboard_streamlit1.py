# dashboard_streamlit1.py — Streamlit-only (Flask stripped out)
# Run with:  streamlit run dashboard_streamlit1.py --server.port 8501

import os
import sqlite3
import pandas as pd
import streamlit as st
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "logs.db")
DB_PATH = os.environ.get("CHATBOT_DB", DEFAULT_DB)


API_URL = os.environ.get("CHATBOT_API", "http://127.0.0.1:5000/query")
HEALTH_URL = os.environ.get("CHATBOT_HEALTH", "http://127.0.0.1:5000/health")
ADMIN_CLEAR_URL = os.environ.get("CHATBOT_CLEAR", "http://127.0.0.1:5000/admin/clear")

st.set_page_config(page_title="Dev Support Chatbot • Dashboard", layout="wide")
st.title("🛠️ Dev Support Chatbot — Live Dashboard")

# --------- DB helpers (WAL so API & dashboard don't block) ----------
def fresh_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                provider TEXT,
                model TEXT
            );
            """
        )
        conn.commit()
    except Exception:
        pass
    return conn

def load_df(limit: int = 1000) -> pd.DataFrame:
    with fresh_conn() as conn:
        df = pd.read_sql_query(
            f"""
            SELECT id, ts, query, response, latency_ms, provider, model
            FROM interactions
            ORDER BY id DESC
            LIMIT {int(limit)}
            """,
            conn,
        )
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
        df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")
        df = df.dropna(subset=["ts", "latency_ms"])
    return df

# --------------------------- Sidebar ---------------------------
with st.sidebar:
    st.subheader("Settings")
    st.caption("These can also be set via env vars: CHATBOT_DB, CHATBOT_API, CHATBOT_HEALTH, CHATBOT_CLEAR")
    st.write(f"**DB:** `{DB_PATH}`")

    api_up = False
    health_info = {}
    try:
        r = requests.get(HEALTH_URL, timeout=2)
        api_up = r.ok
        if r.ok:
            health_info = r.json()
    except Exception:
        api_up = False
    st.write(f"**API health:** {'🟢 up' if api_up else '🔴 down'}")
    if health_info:
        st.caption(f"Provider: {health_info.get('provider')} • Model: {health_info.get('model')}")

    rows = st.slider("Rows to load", min_value=50, max_value=5000, value=1000, step=50)

    if st.button("Clear DB"):
        try:
            r = requests.post(ADMIN_CLEAR_URL, timeout=5)
            if r.ok:
                st.success("Cleared DB.")
            else:
                st.error(f"Clear failed: {r.status_code}")
        except Exception as e:
            st.error(f"Clear failed: {e}")

# --------------------------- Query box ---------------------------
st.subheader("Try a prompt")
col1, col2 = st.columns([3, 1])
with col1:
    user_query = st.text_input("Enter a question:", value="what is kotlin", placeholder="Ask me anything…")
with col2:
    if st.button("Send", type="primary"):
        try:
            r = requests.post(API_URL, json={"query": user_query}, timeout=30)
            if r.ok:
                st.success("Response sent. See below.")
                st.json(r.json())
            else:
                st.error(f"API error: {r.status_code} {r.text[:200]}")
        except Exception as e:
            st.error(f"Request failed: {e}")

# --------------------------- Data & Analytics ---------------------------
df = load_df(rows)
st.subheader("Latest interactions")
if df.empty:
    st.info("No interactions yet. Ask a question above to generate data.")
else:
    st.dataframe(df[["id", "ts", "query", "response", "latency_ms", "provider", "model"]],
                 use_container_width=True, height=320)

    st.subheader("Analytics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Queries", len(df))
    c2.metric("Avg Latency (ms)", f"{round(df['latency_ms'].mean(), 1)}")
    c3.metric("P95 Latency (ms)", f"{int(df['latency_ms'].quantile(0.95))}")
    c4.metric("Unique Queries", df["query"].nunique())

    dft = df.copy()
    dft["bucket"] = dft["ts"].dt.floor("min")
    counts = dft.groupby("bucket").size().rename("count").reset_index()
    lat_by_bucket = dft.groupby("bucket")["latency_ms"].mean().rename("avg_latency_ms").reset_index()
    merged = counts.merge(lat_by_bucket, on="bucket", how="outer").sort_values("bucket").fillna(0)

    st.write("**Queries per minute**")
    st.bar_chart(merged.set_index("bucket")["count"])

    st.write("**Average latency per minute (ms)**")
    st.line_chart(merged.set_index("bucket")["avg_latency_ms"])

    st.write("**Latency distribution (ms)**")
    st.bar_chart(df["latency_ms"])
