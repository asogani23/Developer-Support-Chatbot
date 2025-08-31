import os
import time
import sqlite3
import pandas as pd
import streamlit as st
import requests

DB_PATH = os.environ.get("CHATBOT_DB", "logs.db")
API_URL = os.environ.get("CHATBOT_API", "http://127.0.0.1:5000/query")
HEALTH_URL = os.environ.get("CHATBOT_HEALTH", "http://127.0.0.1:5000/health")
ADMIN_CLEAR_URL = os.environ.get("CHATBOT_CLEAR", "http://127.0.0.1:5000/admin/clear")

st.set_page_config(page_title="Dev Support Chatbot • Dashboard", layout="wide")
st.title("🛠️ Dev Support Chatbot — Live Dashboard")

# --- Session state for persistent UX ---
if "last_payload" not in st.session_state:
    st.session_state["last_payload"] = None
if "last_query" not in st.session_state:
    st.session_state["last_query"] = ""

# Fresh connection each fetch (prevents stale caches)
def fresh_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                provider TEXT,
                model TEXT
            );
        """)
        conn.commit()
    except Exception:
        pass
    return conn

def fetch_df():
    conn = fresh_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM interactions ORDER BY id DESC", conn)
    finally:
        conn.close()
    return df

# Provider/model banner
provider = "unknown"
model = "unknown"
try:
    h = requests.get(HEALTH_URL, timeout=4).json()
    provider = h.get("provider", "unknown")
    model = h.get("model", "unknown")
    use_system_prompt = h.get("use_system_prompt", True)
except Exception as e:
    st.warning(f"Health check failed: {e}")
else:
    if provider == "hf":
        st.info(f"Provider: {provider} • Model: {model} — Local fallback. For best quality, set Gemini/OpenAI.")
    else:
        st.success(f"Provider: {provider} • Model: {model} • System prompt: {'on' if use_system_prompt else 'off'}")

with st.expander("Send a test query", expanded=True):
    q = st.text_input("Query", value=st.session_state.get("last_query", ""), placeholder="e.g., How do I fix a Python KeyError?")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        run_btn = st.button("Send", type="primary", use_container_width=True)
    with c2:
        refresh_btn = st.button("Refresh data", use_container_width=True)
    with c3:
        clear_btn = st.button("Clear all logs", use_container_width=True)
    with c4:
        clear_last_btn = st.button("Hide latest response", use_container_width=True)

    if run_btn and q.strip():
        try:
            r = requests.post(API_URL, json={"query": q.strip()}, timeout=30)
            if r.ok:
                payload = r.json()
                # Persist for after-rerun display
                st.session_state["last_payload"] = payload
                st.session_state["last_query"] = q.strip()
                # Show immediately
                st.success(
                    f"Response ({payload.get('latency_ms')} ms @ {payload.get('timestamp')}) — "
                    f"{payload.get('provider')}/{payload.get('model')}"
                )
                st.code((payload.get("response", "") or "")[:5000])
            else:
                st.error(f"API error {r.status_code}: {r.text[:300]}")
        except Exception as e:
            st.error(f"Request failed: {e}")
        # Allow DB commit then rerun so tables/charts update, while we keep the latest response via session_state
        time.sleep(0.25)
        st.rerun()

    if refresh_btn:
        st.rerun()

    if clear_btn:
        ok = False
        try:
            resp = requests.post(ADMIN_CLEAR_URL, timeout=5)
            ok = resp.ok
        except Exception:
            ok = False
        if not ok:
            try:
                conn = fresh_conn()
                conn.execute("DELETE FROM interactions;")
                conn.execute("VACUUM;")
                conn.commit()
                conn.close()
                ok = True
            except Exception as e:
                st.error(f"Could not clear logs: {e}")
        if ok:
            st.success("Logs cleared.")
            # Also clear the "latest response" panel when logs are cleared
            st.session_state["last_payload"] = None
            st.session_state["last_query"] = ""
            time.sleep(0.15)
            st.rerun()

    if clear_last_btn:
        st.session_state["last_payload"] = None
        st.session_state["last_query"] = ""
        st.rerun()

# Persistent "Most recent response" card
if st.session_state.get("last_payload"):
    p = st.session_state["last_payload"]
    st.subheader("🧠 Most recent response")
    with st.container():
        st.markdown(f"**{p.get('timestamp','')}** — *{p.get('provider','?')}/{p.get('model','?')}*")
        st.write(f"**Q:** {st.session_state.get('last_query','')}")
        with st.expander("Show full response", expanded=True):
            st.code(p.get("response",""))

st.markdown("---")

# Always fetch fresh data
df = fetch_df()

# Latest responses (large, readable)
st.subheader("🆕 Latest responses")
if df.empty:
    st.info("No queries yet.")
else:
    latest = df.sort_values("id", ascending=False).head(10)
    for _, row in latest.iterrows():
        with st.container():
            st.markdown(f"**{row['ts']}** — *{row.get('provider','?')}/{row.get('model','?')}*")
            st.write(f"**Q:** {row['query']}")
            with st.expander("Show full response", expanded=True):
                st.code(row['response'])

st.markdown("---")
st.subheader("📒 Full Query Log (compact)")
if df.empty:
    st.info("No data to display.")
else:
    df_pretty = df.rename(columns={
        "ts": "Timestamp",
        "query": "Query",
        "response": "Response",
        "latency_ms": "Latency (ms)",
        "provider": "Provider",
        "model": "Model",
    })
    df_pretty["Response"] = df_pretty["Response"].str.slice(0, 200)
    st.dataframe(df_pretty.drop(columns=["id"]), use_container_width=True, height=320)

st.markdown("---")
st.subheader("📈 Analytics")
if df.empty:
    st.info("No data to display yet.")
else:
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Queries (all time)", len(df))
    with c2:
        st.metric("Unique Questions", df["query"].nunique())
    with c3:
        st.metric("Avg Latency (ms)", round(df["latency_ms"].mean(), 1))
    with c4:
        st.metric("P95 Latency (ms)", int(df["latency_ms"].quantile(0.95)) if len(df) >= 2 else int(df["latency_ms"].max()))

    df_time = (
        df.assign(bucket=df["ts"].dt.floor("min"))
          .groupby("bucket").size().sort_index().rename("count").reset_index()
    )
    if not df_time.empty:
        df_time["cumulative"] = df_time["count"].cumsum()
        st.write("**Queries per minute (bar)**")
        st.bar_chart(df_time.set_index("bucket")["count"])
        st.write("**Cumulative queries (line)**")
        st.line_chart(df_time.set_index("bucket")["cumulative"])

    st.write("**Top repeated queries**")
    top_queries = (
        df.groupby("query").size().sort_values(ascending=False).head(10).rename("Count").reset_index()
    )
    st.dataframe(top_queries, use_container_width=True)

    st.write("**Latency distribution (ms)**")
    st.bar_chart(df["latency_ms"])
