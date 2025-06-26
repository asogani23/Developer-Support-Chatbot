import streamlit as st
import pandas as pd
import datetime
import requests

# Simulated data storage (replace with a real database in production)
data = {
    "Timestamp": [],
    "Query": [],
    "Response": []
}

# Function to log query and response
def log_query(query, response):
    global data
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["Timestamp"].append(timestamp)
    data["Query"].append(query)
    data["Response"].append(response)

# Simulated Chatbot API call
def chatbot_api_simulation(query):
    url = "http://127.0.0.1:5000/query"
    response = requests.post(url, json={"query": query})
    if response.status_code == 200:
        return response.json().get("response", "No response")
    else:
        return "Error connecting to chatbot API."

# Streamlit UI
st.title("Developer Support Chatbot Dashboard")

# Input Section
st.header("Interact with Chatbot")
query = st.text_input("Enter your query:", key="query_input_box")
if st.button("Submit"):
    response = chatbot_api_simulation(query)
    log_query(query, response)
    st.success(f"Chatbot Response: {response}")

# Log Display Section
st.header("Query Log")
if data["Timestamp"]:
    df = pd.DataFrame(data)
    st.dataframe(df)
else:
    st.write("No queries logged yet.")

# Analytics Section
st.header("Analytics")
if data["Timestamp"]:
    df = pd.DataFrame(data)
    query_count = df["Query"].count()
    st.metric("Total Queries", query_count)
    st.bar_chart(df["Query"].value_counts())
else:
    st.write("No data to display.")
