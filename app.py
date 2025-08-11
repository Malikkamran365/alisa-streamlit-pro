import os
import io
import time
import sqlite3
from typing import List, Dict, Any, Optional

import streamlit as st
import requests
# ---- Real-time clock helpers ----
def fetch_now(tz: str = "Asia/Karachi") -> str:
    try:
        r = requests.get(f"http://worldtimeapi.org/api/timezone/{tz}", timeout=6)
        if r.status_code == 200:
            j = r.json()
            dt = j.get("datetime", "")
            if dt:
                date_part, time_part = dt.split("T", 1)
                time_part = time_part.split("+")[0].split("Z")[0][:8]
                return f"{date_part} {time_part} ({tz})"
    except Exception:
        pass
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M (server)")
# Optional deps
try:
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    from supabase import create_client
except Exception:
    create_client = None

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="ALISA • Gen Z Mentor", page_icon="✨", layout="centered")

PRIMARY_EMOJI = "✨"
BRAND = "ALISA"
TAGLINE = "Your Study & Life Copilot"

def hero():
    st.markdown(f"""
    <div style="text-align:center; padding: 12px 0 4px 0;">
        <div style="font-size:40px; font-weight:800; letter-spacing:0.5px">{PRIMARY_EMOJI} {BRAND}</div>
        <div style="font-size:18px; opacity:0.85">{TAGLINE}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.title("⚙️ Settings")
    st.markdown("Provide an **OpenAI-compatible** API key. Works with OpenAI or any compatible endpoint.")
    default_base = st.secrets.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_base = st.text_input("Base URL", value=default_base)
    # Sidebar key is optional; we also read from Secrets/env automatically.
    api_key = st.text_input("API Key (optional — Secrets also used)", type="password")
    model = st.text_input("Model", value=st.secrets.get("MODEL", "gpt-4o-mini"))
    lang = st.selectbox("Language", ["English", "اردو (Urdu)"], index=0)
    voice_tts = st.checkbox("Enable Voice Output (TTS)", value=False)
    stt_enabled = st.checkbox("Enable Voice Input (STT)", value=False)
    st.caption("Tip: If you leave API Key empty here, the app will use OPENAI_API_KEY from Secrets/env.")

    st.divider()
    st.subheader("🧠 Memory backend")
    mem_backend = st.selectbox("Backend", ["SQLite (built-in)", "Supabase (optional)"], index=0)
    if mem_backend == "Supabase (optional)":
        st.caption("Set SUPABASE_URL and SUPABASE_KEY in Secrets.")

    st.divider()
    default_prompt = (
    "You are ALISA — a warm, encouraging, Gen Z mentor for students, created and founded by Malik Kamran. "
    "Always answer as ALISA and never mention OpenAI or any other company as your creator. "
    "If someone asks about your founder, always say: 'I was founded by Malik Kamran, the visionary behind ALISA. " )
    
    
    
    if lang.startswith("اردو"):
        default_prompt += "Reply in Urdu unless the user asks for English. "
    else:
        default_prompt += "Reply in English unless the user asks for Urdu. "
    system_prompt = st.text_area("System Prompt", value=st.secrets.get("SYSTEM_PROMPT", default_prompt), height=160)

# ---------- SESSION ----------
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, Any]] = [{"role": "system", "content": "You are ALISA."}]
if "name" not in st.session_state:
    st.session_state.name = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = str(int(time.time()))

# ---------- DB (SQLite) ----------
DB_PATH = os.getenv("ALISA_DB_PATH", "alisa.db")

def sqlite_init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_name TEXT,
            role TEXT,
            content TEXT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn

def sqlite_save_messages(session_id: str, user_name: str, messages: List[Dict[str, str]]):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for m in messages:
        if m["role"] == "system":
            continue
        cur.execute("INSERT INTO messages (session_id, user_name, role, content) VALUES (?, ?, ?, ?);",
                    (session_id, user_name, m["role"], m["content"]))
    conn.commit()
    conn.close()

def sqlite_load_messages(session_id: Optional[str]=None, user_name: Optional[str]=None, limit: int = 50) -> List[Dict[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if session_id:
        cur.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?;", (session_id, limit))
    else:
        cur.execute("SELECT role, content FROM messages WHERE user_name=? ORDER BY id DESC LIMIT ?;", (user_name, limit))
    rows = cur.fetchall()
    conn.close()
    return [{"role": r, "content": c} for (r, c) in rows[::-1]]

# ---------- Supabase (optional) ----------
def supabase_client():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key or not create_client:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

def supabase_save_messages(client, session_id: str, user_name: str, messages: List[Dict[str, str]]):
    if not client: return
    payload = [
        {"session_id": session_id, "user_name": user_name, "role": m["role"], "content": m["content"]}
        for m in messages if m["role"] != "system"
    ]
    try:
        client.table("messages").insert(payload).execute()
    except Exception as e:
        st.warning(f"Supabase insert failed: {e}")

def supabase_load_messages(client, session_id: Optional[str]=None, user_name: Optional[str]=None, limit: int=50):
    if not client: return []
    try:
        query = client.table("messages").select("role,content").order("id", desc=True).limit(limit)
        if session_id:
            query = query.eq("session_id", session_id)
        elif user_name:
            query = query.eq("user_name", user_name)
        data = query.execute().data or []
        data.reverse()
        return [{"role": d["role"], "content": d["content"]} for d in data]
    except Exception as e:
        st.warning(f"Supabase fetch failed: {e}")
        return []

# ---------- Helpers ----------
def get_api_key() -> str:
    """Sidebar key -> env -> Secrets."""
    return (api_key or os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")).strip()

def get_model() -> str:
    """Sidebar model -> env -> Secrets -> default."""
    return (model or os.getenv("MODEL") or st.secrets.get("MODEL", "gpt-4o-mini")).strip()

# ---------- LLM CALL ----------
def call_openai_compatible(messages: List[Dict[str, str]], system_prompt: str) -> str:
    used_key = get_api_key()
    if not used_key:
        return "⚠️ No API key found. Add it in the sidebar or Secrets."
    used_model = get_model()
# Inject live date/time into system prompt
    now_str = fetch_now()
    system_prompt = f"{system_prompt}\n\nCurrent date and time: {now_str}"
    url = f"{api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": used_model,
        "messages": [{"role": "system", "content": system_prompt}] +
                    [{"role": m["role"], "content": m["content"]}
                     for m in messages if m["role"] in ("user", "assistant")],
        "temperature": 0.7,
        "max_tokens": 700
    }
    headers = {"Authorization": f"Bearer {used_key}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            return f"⚠️ API error {r.status_code}: {r.text[:400]}"
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content or "⚠️ Empty response from model."
    except Exception as e:
        return f"⚠️ Request failed: {e}"

# ---------- STT (Transcription) ----------
def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    key = get_api_key()
    if not key:
        return "⚠️ No API key for STT."
    try:
        url = f"{api_base.rstrip('/')}/audio/transcriptions"
        files = {"file": (filename, audio_bytes, "audio/wav")}
        data = {"model": st.secrets.get("WHISPER_MODEL", "whisper-1")}
        headers = {"Authorization": f"Bearer {key}"}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=120)
        if resp.status_code != 200:
            return f"⚠️ STT error {resp.status_code}: {resp.text[:300]}"
        j = resp.json()
        return j.get("text", "")
    except Exception as e:
        return f"⚠️ STT failed: {e}"

# ---------- TTS ----------
def tts_gtts(text: str, lang_code: str):
    if not gTTS:
        st.warning("gTTS not installed; cannot synthesize audio.")
        return None
    try:
        mp3 = io.BytesIO()
        gTTS(text=text, lang=lang_code).write_to_fp(mp3)
        mp3.seek(0)
        return mp3.read()
    except Exception as e:
        st.warning(f"TTS failed: {e}")
        return None

# ---------- UI ----------
hero()

with st.container():
    st.markdown("""
    <div style="text-align:center; margin-top:6px; margin-bottom:18px;">
        <p style="font-size:16px; opacity:0.9">
            Friendly study plans • Wellness check-ins • Simple motivation • Urdu/English
        </p>
    </div>
    """, unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Your name", value=st.session_state.name, placeholder="e.g., Kamran")
    if name and name != st.session_state.name:
        st.session_state.name = name
with col2:
    st.session_state.session_id = st.text_input("Session ID", value=st.session_state.session_id)

mem_col1, mem_col2, mem_col3 = st.columns(3)
with mem_col1:
    load_scope = st.selectbox("Load memory by", ["Session", "User"], index=0)
with mem_col2:
    if st.button("🔁 Load Previous Messages"):
        if mem_backend == "SQLite (built-in)":
            loaded = sqlite_load_messages(session_id=st.session_state.session_id) if load_scope=="Session" else sqlite_load_messages(user_name=st.session_state.name)
        else:
            client = supabase_client()
            loaded = supabase_load_messages(client, session_id=st.session_state.session_id) if load_scope=="Session" else supabase_load_messages(client, user_name=st.session_state.name)
        st.session_state.messages = [{"role":"system","content":"You are ALISA."}] + loaded
with mem_col3:
    if st.button("💾 Save This Chat"):
        msgs_to_save = [m for m in st.session_state.messages if m["role"] != "system"]
        if mem_backend == "SQLite (built-in)":
            sqlite_save_messages(st.session_state.session_id, st.session_state.name, msgs_to_save)
            st.success("Saved to SQLite.")
        else:
            client = supabase_client()
            supabase_save_messages(client, st.session_state.session_id, st.session_state.name, msgs_to_save)
            st.success("Saved to Supabase (if configured).")

st.markdown("---")

st.markdown("### Chat")
st.write("Type or use voice. Messages stay on this page until you save them to memory.")

user_text = st.chat_input("Type your message…")

audio_bytes = None
audio_file = st.file_uploader("Optional: record or upload voice note (wav/mp3/m4a)", type=["wav","mp3","m4a"], accept_multiple_files=False)
if audio_file is not None:
    audio_bytes = audio_file.read()

if stt_enabled and audio_bytes and st.button("🎙️ Transcribe & Send"):
    text_from_audio = transcribe_audio(audio_bytes, filename=audio_file.name or "audio.wav")
    if text_from_audio and not text_from_audio.startswith("⚠️"):
        if st.session_state.name:
            text_from_audio = f"My name is {st.session_state.name}. " + text_from_audio
        st.session_state.messages.append({"role":"user","content": text_from_audio})
    else:
        st.warning(text_from_audio or "No text decoded from audio.")

if user_text:
    if st.session_state.name:
        user_text = f"My name is {st.session_state.name}. " + user_text
    st.session_state.messages.append({"role":"user","content": user_text})

for m in st.session_state.messages[1:]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if len(st.session_state.messages) >= 2 and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            reply = call_openai_compatible(st.session_state.messages, system_prompt)
            st.markdown(reply)
            if voice_tts and reply and not reply.startswith("⚠️"):
                lang_code = "ur" if lang.startswith("اردو") else "en"
                audio = tts_gtts(reply, lang_code)
                if audio:
                    st.audio(audio, format="audio/mp3")
    st.session_state.messages.append({"role":"assistant","content": reply})

with st.expander("ℹ️ Tips / Deployment"):
    st.markdown("""
- **API**: Put your key in the sidebar *or* set `OPENAI_API_KEY` in **Secrets**. Model can be set via `MODEL`.
- **Provider**: To use a non-OpenAI provider, set **OPENAI_BASE_URL** and a supported **MODEL**.
- **Memory**: Save to SQLite (local file) or Supabase. For Supabase, create a `messages` table with columns:  
  `id bigserial primary key, session_id text, user_name text, role text, content text, created_at timestamp default now()`.
- **Voice**:
  - **STT**: Requires a Whisper-compatible `/audio/transcriptions` endpoint.
  - **TTS**: Uses `gTTS`; enable in sidebar to hear replies.
- **Deploy**: Streamlit Community Cloud or Hugging Face Spaces → add Secrets → Deploy.


    """)
