# 🛠️ Developer-Support Chatbot

A lightweight **AI troubleshooting assistant** that answers developer questions, logs every interaction, and gives you live analytics.

| Component | Tech | Purpose |
|-----------|------|---------|
| **Flask API** | Python + Hugging Face `transformers` | `/query` endpoint backed by GPT-2 (plug-and-play for any LLM) |
| **VS Code Extension** | TypeScript (packaged in `dist/`) | Surfaced answers directly in the IDE |
| **Streamlit Dashboard** | Python + Streamlit | Real-time log viewer & basic analytics |

> 🔒 **Note:** This repo contains only open-source code and demo assets—no private keys or proprietary data.

---

## ✨ Key Features

- **Natural-language Q&A** for syntax errors, API usage, and best-practice questions  
- **Single POST endpoint** (`/query`) for easy integration into Slack bots, webhooks, or CLI tools  
- **IDE integration** (VS Code) for in-context answers without leaving your editor  
- **Live dashboard** to inspect query history, success metrics, and popular topics

---

## 🚀 Quick Start

```bash
# 1. Clone and install Python deps
git clone https://github.com/<your-username>/developer-support-chatbot.git
cd developer-support-chatbot
pip install -r requirements.txt   # flask, transformers, streamlit, requests

# 2. Run the Flask API
python app.py          # => http://127.0.0.1:5000/query

# 3. (Optional) Open the Streamlit dashboard in a second terminal
streamlit run dashboard.py        # => http://localhost:8501
