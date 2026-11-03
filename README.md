# BLACKFISH01 / Hai

Telegram + Flask session panel (Pyrogram runtime, Telethon export).

## Structure
- `app.py` — Flask web app
- `bot.py` — Telegram bot worker
- `config.py` — env config (SECRET_KEY auto via `.flask_secret`)
- `Nexa/` — core modules (auth, admin, sessions, broadcast, DB)
- `templates/` — web UI

## Deploy
Set env: `BOT_TOKEN`, `API_ID`, `API_HASH`, `MONGODB_URI`, `WEB_APP_URL`, `API_BASE_URL`, `ADMIN_PASSWORD`, `LOG_CHANNEL`, `ADMIN_IDS`

`SECRET_KEY` is **not required** — generated automatically into `.flask_secret`.

Procfile:
- `web`: `python app.py`
- `worker`: `python bot.py`
