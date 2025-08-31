import os
import time
import sqlite3
from contextlib import closing
from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------------------
# Provider auto-detect
# ---------------------------
def detect_provider():
    # Prefer Gemini if any Gemini-like key is present (no env var required)
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return "gemini"
    # Then OpenAI
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    # Fallback to HF
    return "hf"

PROVIDER = (os.environ.get("PROVIDER") or "").strip().lower() or detect_provider()

# Optional: .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DB_PATH = os.environ.get("CHATBOT_DB", "logs.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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
        """
        )
        conn.commit()

def log_interaction(ts, query, response, latency_ms, provider, model):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO interactions (ts, query, response, latency_ms, provider, model) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, query, response, latency_ms, provider, model)
        )
        conn.commit()

# ---------------------------
# Model setup
# ---------------------------
_openai_client = None
_openai_model = None
_gemini_model = None
_hf_pipe = None
_hf_model_name = None

USE_SYSTEM_PROMPT = not bool(int(os.getenv("DISABLE_SYSTEM_PROMPT", "0")))

def _system_prompt():
    return (
        "You are a concise developer support assistant. "
        "Explain clearly, provide short code examples when helpful, and avoid repetition."
    )

def _init_openai():
    global _openai_client, _openai_model
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI provider")
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=api_key)
        _openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    except Exception:
        import openai
        openai.api_key = api_key
        _openai_client = openai
        _openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    return "openai", _openai_model

def _init_gemini():
    global _gemini_model
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY (or GEMINI_API_KEY) is required for Gemini provider")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    _gemini_model = genai.GenerativeModel(model_name)
    return "gemini", model_name

def _init_hf():
    global _hf_pipe, _hf_model_name
    candidates = [
        ("text2text-generation", "google/flan-t5-base"),
        ("text2text-generation", "google/flan-t5-small"),
        ("text-generation", "gpt2"),
    ]
    last_err = None
    for task, name in candidates:
        try:
            from transformers import pipeline
            _hf_pipe = pipeline(task, model=name)
            _hf_model_name = name
            return "hf", name
        except Exception as e:
            last_err = e
    raise RuntimeError(f"HF init failed: {last_err}")

def _ensure_provider():
    if PROVIDER == "openai":
        return _init_openai()
    elif PROVIDER == "gemini":
        return _init_gemini()
    else:
        return _init_hf()

def _generate_openai(user_query: str) -> tuple[str, str]:
    messages = [{"role":"user","content":user_query}]
    if USE_SYSTEM_PROMPT:
        messages.insert(0, {"role":"system","content":_system_prompt()})
    try:
        resp = _openai_client.chat.completions.create(
            model=_openai_model, temperature=0.3, max_tokens=300, messages=messages
        )
        text = resp.choices[0].message.content.strip()
    except Exception:
        resp = _openai_client.ChatCompletion.create(
            model=_openai_model, temperature=0.3, max_tokens=300, messages=messages
        )
        text = resp["choices"][0]["message"]["content"].strip()
    return text, _openai_model

def _generate_gemini(user_query: str) -> tuple[str, str]:
    if USE_SYSTEM_PROMPT:
        parts = [_system_prompt(), user_query]
    else:
        parts = [user_query]
    result = _gemini_model.generate_content(parts)
    text = (result.text or "").strip()
    return text, os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def _generate_hf(user_query: str) -> tuple[str, str]:
    task = getattr(_hf_pipe, "task", "")
    if USE_SYSTEM_PROMPT:
        prompt = f"{_system_prompt()}\n\nUser: {user_query}\nAssistant:"
    else:
        prompt = user_query
    if task == "text2text-generation":
        out = _hf_pipe(prompt, max_new_tokens=220)
        text = out[0]["generated_text"].strip()
    else:
        out = _hf_pipe(
            prompt,
            max_new_tokens=220,
            do_sample=False,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
            return_full_text=False,
        )
        text = out[0]["generated_text"].strip()
    return text, _hf_model_name

# ---------------------------
# Flask app
# ---------------------------
app = Flask(__name__)
CORS(app)
provider_name, model_name = _ensure_provider()
init_db()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "provider": provider_name, "model": model_name, "use_system_prompt": USE_SYSTEM_PROMPT})

@app.route('/query', methods=['POST'])
def query():
    import datetime as _dt
    start = time.perf_counter()
    data = request.get_json(silent=True) or {}
    user_query = (data.get("query") or "").strip()

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    try:
        if provider_name == "openai":
            answer, mdl = _generate_openai(user_query)
        elif provider_name == "gemini":
            answer, mdl = _generate_gemini(user_query)
        else:
            answer, mdl = _generate_hf(user_query)
    except Exception as e:
        answer, mdl = f"(provider_error) {e}", "n/a"

    latency_ms = int((time.perf_counter() - start) * 1000)
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    try:
        log_interaction(ts, user_query, answer, latency_ms, provider_name, mdl)
    except Exception as e:
        print("Logging error:", repr(e))

    return jsonify({
        "response": answer,
        "latency_ms": latency_ms,
        "timestamp": ts,
        "provider": provider_name,
        "model": mdl,
        "use_system_prompt": USE_SYSTEM_PROMPT
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
