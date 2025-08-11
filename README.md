
# ALISA — Streamlit Pro Pack (Memory + Voice + Urdu/English + Branding)

This pack adds:
- 🧠 **Long-term memory**: SQLite (built-in) or **Supabase** table.
- 🎙️ **Voice input (STT)**: Upload or record audio → transcribe via OpenAI-compatible `/audio/transcriptions`.
- 🔊 **Voice output (TTS)**: gTTS for spoken replies.
- 🏠 **Branded landing** + clean chat page.
- 🌐 **Urdu/English toggle** with prompt steering.

## Deploy (Streamlit Community Cloud)
1. Push files to a **public GitHub repo**.
2. Deploy a new app and select `app.py`.
3. In **Secrets**, add at minimum:
   - `OPENAI_API_KEY`
   - (optional) `OPENAI_BASE_URL`, `MODEL`
   - (optional) `WHISPER_MODEL` for STT
   - (optional) `SUPABASE_URL`, `SUPABASE_KEY` for remote memory
4. Click **Deploy**.

## Supabase Setup
Create table **messages**:
```sql
create table if not exists messages (
  id bigserial primary key,
  session_id text,
  user_name text,
  role text,
  content text,
  created_at timestamp default now()
);
```
Then add `SUPABASE_URL` and `SUPABASE_KEY` to Secrets.

## Local Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- On first run, click **Save This Chat** to persist messages (SQLite or Supabase).
- STT: Your provider must expose a Whisper-compatible `/audio/transcriptions` endpoint.
- TTS: gTTS requires internet access to synthesize MP3.
