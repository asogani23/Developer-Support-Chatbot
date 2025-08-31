import os
import time
import datetime
import pandas as pd
import streamlit as st
import requests

# === Config ===
API_URL = os.environ.get("CHATBOT_API", "http://127.0.0.1:5000/query")

st.title("Developer Support Chatbot Dashboard")

# ---- Inject minimal CSS just for the response card ----
st.markdown(
    """
    <style>
      .response-card {
        border: 1px solid #e5e7eb;           /* light gray */
        background: linear-gradient(180deg, #f7fff9 0%, #eefdf4 100%);
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.06);
        margin-top: 8px;
        max-height: 460px;                    /* keep page tidy on long answers */
        overflow: auto;                       /* scroll long responses */
      }
      .response-title {
        font-weight: 700;
        font-size: 1.05rem;
        color: #065f46;                       /* emerald-800 */
        margin-bottom: 8px;
      }
      .response-body {
        font-size: 1.0rem;
        line-height: 1.6;
        color: #0f172a;                       /* slate-900 */
      }
      .response-body code {
        background: #f3f4f6;                  /* gray-100 */
        padding: 2px 6px;
        border-radius: 6px;
      }
      .response-body pre {
        background: #0b1020;                  /* dark block for code fences */
        color: #e5e7eb;
        padding: 12px 14px;
        border-radius: 10px;
        overflow: auto;
      }
      .response-body ul, .response-body ol {
        margin-left: 1.2rem;
      }
      .response-body h1, .response-body h2, .response-body h3 {
        margin-top: 0.6rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# === Persistent storage (prevents reset on each rerun) ===
if "data" not in st.session_state:
    st.session_state.data = {
        "Timestamp": [],
        "Query": [],
        "Response": [],
        "Latency_ms": [],  # track response time
    }
if "last_response" not in st.session_state:
    st.session_state.last_response = ""

# Function to log query and response
def log_query(query, response, latency_ms):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.data["Timestamp"].append(timestamp)
    st.session_state.data["Query"].append(query)
    st.session_state.data["Response"].append(response)
    st.session_state.data["Latency_ms"].append(latency_ms)
    st.session_state.last_response = response  # show nicely in the card

# Chatbot API call with latency measurement
def chatbot_api_call(query):
    try:
        start = time.perf_counter()
        r = requests.post(API_URL, json={"query": query}, timeout=30)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if r.status_code == 200:
            j = r.json()
            resp = j.get("response") or j.get("answer") or str(j)
            return resp, latency_ms
        else:
            return f"API error: {r.status_code}", latency_ms
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000) if "start" in locals() else 0
        return f"Error connecting to chatbot API: {e}", latency_ms

# ================= UI =================

# Input Section
st.header("Interact with Chatbot")
query = st.text_input("Enter your query:", key="query_input_box")
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Submit"):
        response, latency = chatbot_api_call(query)
        log_query(query, response, latency)
with col2:
    if st.button("Clear Analytics / History"):
        st.session_state.data = {"Timestamp": [], "Query": [], "Response": [], "Latency_ms": []}
        st.session_state.last_response = ""
        st.info("Cleared.")

# Beautiful response card (only the output area)
if st.session_state.last_response:
    st.markdown(
        f"""
        <div class="response-card">
          <div class="response-title">Chatbot Response</div>
          <div class="response-body">
            {st.session_state.last_response}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Log Display Section (unchanged)
st.header("Query Log")
if st.session_state.data["Timestamp"]:
    df = pd.DataFrame(st.session_state.data)
    st.dataframe(df, use_container_width=True, height=260)
else:
    st.write("No queries logged yet.")

# Analytics Section (unchanged)
st.header("Analytics")
if st.session_state.data["Timestamp"]:
    df = pd.DataFrame(st.session_state.data)

    total = df["Query"].count()
    st.metric("Total Queries", total)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df["Latency_ms"] = pd.to_numeric(df["Latency_ms"], errors="coerce")
    df = df.dropna(subset=["Timestamp"])

    df["bucket_min"] = df["Timestamp"].dt.floor("min")
    per_min = df.groupby("bucket_min").size().rename("count").reset_index()
    st.write("**Queries per minute**")
    st.bar_chart(per_min.set_index("bucket_min")["count"])

    if df["Latency_ms"].notna().any():
        st.write("**Latency over time (ms)**")
        st.line_chart(df.set_index("Timestamp")["Latency_ms"])

    st.write("**Top repeated queries**")
    topq = df.groupby("Query").size().sort_values(ascending=False).head(10).rename("Count").reset_index()
    st.dataframe(topq, use_container_width=True)
else:
    st.write("No data to display.")
