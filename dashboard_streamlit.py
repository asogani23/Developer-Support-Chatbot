import os
import time
import datetime
import pandas as pd
import streamlit as st
import requests

# === Config ===
API_URL = os.environ.get("CHATBOT_API", "http://127.0.0.1:5000/query")

st.title("Developer Support Chatbot Dashboard")

# === Persistent storage (prevents reset on each rerun) ===
if "data" not in st.session_state:
    st.session_state.data = {
        "Timestamp": [],
        "Query": [],
        "Response": [],
        "Latency_ms": [],  # NEW: track response time
    }

# Function to log query and response
def log_query(query, response, latency_ms):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.data["Timestamp"].append(timestamp)
    st.session_state.data["Query"].append(query)
    st.session_state.data["Response"].append(response)
    st.session_state.data["Latency_ms"].append(latency_ms)

# Chatbot API call with latency measurement
def chatbot_api_call(query):
    try:
        start = time.perf_counter()
        r = requests.post(API_URL, json={"query": query}, timeout=30)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if r.status_code == 200:
            # Try common response shapes
            j = r.json()
            resp = j.get("response") or j.get("answer") or str(j)
            return resp, latency_ms
        else:
            return f"API error: {r.status_code}", latency_ms
    except Exception as e:
        # Still return a latency estimate
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
        st.success(f"Chatbot Response: {response}")
with col2:
    if st.button("Clear Analytics / History"):
        st.session_state.data = {"Timestamp": [], "Query": [], "Response": [], "Latency_ms": []}
        st.info("Cleared.")

# Log Display Section
st.header("Query Log")
if st.session_state.data["Timestamp"]:
    df = pd.DataFrame(st.session_state.data)
    st.dataframe(df, use_container_width=True, height=260)
else:
    st.write("No queries logged yet.")

# Analytics Section
st.header("Analytics")
if st.session_state.data["Timestamp"]:
    df = pd.DataFrame(st.session_state.data)

    # Top-level metrics
    total = df["Query"].count()
    st.metric("Total Queries", total)

    # Parse timestamps and build time buckets
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df["Latency_ms"] = pd.to_numeric(df["Latency_ms"], errors="coerce")
    df = df.dropna(subset=["Timestamp"])  # keep good rows

    # Queries per minute (fixes the “always 1” issue from value_counts of unique strings)
    df["bucket_min"] = df["Timestamp"].dt.floor("min")
    per_min = df.groupby("bucket_min").size().rename("count").reset_index()
    st.write("**Queries per minute**")
    st.bar_chart(per_min.set_index("bucket_min")["count"])

    # Latency over time (ms)
    if df["Latency_ms"].notna().any():
        st.write("**Latency over time (ms)**")
        st.line_chart(df.set_index("Timestamp")["Latency_ms"])

    # (Optional) Top repeated queries — keep this if you repeat prompts often
    st.write("**Top repeated queries**")
    topq = df.groupby("Query").size().sort_values(ascending=False).head(10).rename("Count").reset_index()
    st.dataframe(topq, use_container_width=True)
else:
    st.write("No data to display.")
