import os
import time
import sqlite3
from contextlib import closing
from flask import Flask, request, jsonify
from flask_cors import CORS

# Optional: swap to a stronger model later (e.g., OpenAI, Gemini). For now, keep it offline/demo-friendly.
try:
    from transformers import pipeline
    nlp = pipeline("text-generation", model="gpt2")
    _HAS_TRANSFORMERS = True
except Exception:
    _HAS_TRANSFORMERS = False
    nlp = None

DB_PATH = os.environ.get("CHATBOT_DB", "logs.db")

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
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

def log_interaction(ts, query, response, latency_ms):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO interactions (ts, query, response, latency_ms) VALUES (?, ?, ?, ?)",
            (ts, query, response, latency_ms)
        )
        conn.commit()

app = Flask(__name__)
CORS(app)
init_db()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route('/query', methods=['POST'])
def query():
    start = time.perf_counter()
    data = request.get_json(silent=True) or {}
    user_query = (data.get("query") or "").strip()

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    # Generate a response (fallback to a simple echo if transformers not available)
    if _HAS_TRANSFORMERS and nlp is not None:
        # Keep generation short/snappy for demo
        generation = nlp(user_query, max_length=100, num_return_sequences=1, do_sample=False)
        model_text = generation[0].get("generated_text", "").strip()
    else:
        model_text = f"(demo) You asked: {user_query}. Replace GPT-2 with your preferred model."

    latency_ms = int((time.perf_counter() - start) * 1000)

    # Log to SQLite with ISO timestamp
    import datetime as _dt
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    try:
        log_interaction(ts, user_query, model_text, latency_ms)
    except Exception as e:
        # Don't fail the request just because logging failed
        print("Logging error:", repr(e))

    return jsonify({
        "response": model_text,
        "latency_ms": latency_ms,
        "timestamp": ts
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
