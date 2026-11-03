# BLACKFISH01 / Hai

Telegram + Flask session panel with automatic Telethon export.

## Structure

```
app.py                 # Flask web app
bot.py                 # Pyrogram bot worker
config.py              # Env config (SECRET_KEY auto via .flask_secret)
Nexa/
  auth_routes.py       # Phone/OTP login API
  admin_routes.py      # Admin panel APIs
  session_manager.py   # Live session tracking
  session_tools.py     # Session health checks
  telethon_export.py   # Pyrogram → Telethon string
  broadcaster.py       # Ads broadcaster
  database.py          # MongoDB
  bot_zip.py           # Session zip download
  logs.py
templates/             # Web UI
```

## SECRET_KEY (Option A)

No manual key. On first run the app creates `.flask_secret` and reuses it.

## Required env vars

```
BOT_TOKEN=
API_ID=
API_HASH=
MONGODB_URI=
DB_NAME=nexa_bot
WEB_APP_URL=
API_BASE_URL=
ADMIN_PASSWORD=
LOG_CHANNEL=
```

## Run

```
pip install -r requirements.txt
python app.py   # web
python bot.py   # worker
```
