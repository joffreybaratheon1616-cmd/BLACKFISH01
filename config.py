import os

def _int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default

def _float(key, default):
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default

# ---------- Telegram ----------
API_ID   = _int("API_ID", 32208414)
API_HASH = os.environ.get("API_HASH", "628f11c05a44c8dda4b006e66f4bf7df")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9194448928:AAFGMxeWk-uFD5b-t987YRAzLiMrgIxviA4")

LOG_CHANNEL = _int("LOG_CHANNEL", -1003919524886)
CHANNEL_ID  = LOG_CHANNEL
ADMIN_IDS   = [8580367479, 8694029886]

# ---------- Web ----------
def _resolve_secret_key() -> str:
    """Fully automatic Flask cookie signing key (Option A).

    You do NOT set SECRET_KEY in env or code.
    On first run a random key is written to .flask_secret and reused forever.
    """
    import secrets
    path = os.path.join(os.getcwd(), ".flask_secret")
    try:
        if os.path.isfile(path):
            stored = open(path, "r", encoding="utf-8").read().strip()
            if len(stored) >= 32:
                return stored
    except Exception:
        pass
    key = secrets.token_hex(32)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(key)
    except Exception:
        pass
    return key

SECRET_KEY = _resolve_secret_key()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

WEB_APP_URL     = os.environ.get("WEB_APP_URL", "https://hai-3f722c58b44b.herokuapp.com")
API_BASE_URL    = os.environ.get("API_BASE_URL", "https://hai-3f722c58b44b.herokuapp.com")
ADMIN_PANEL_URL = os.environ.get("ADMIN_PANEL_URL", "https://hai-3f722c58b44b.herokuapp.com" + "/admin")

BACKGROUND_VIDEO = os.environ.get(
    "BACKGROUND_VIDEO",
    "https://tmpfiles.org/woAccPGwLvqZ/"
    "angelchan_on_x_new_set_release_secret_life_of_a_naughty_cat_m.mp4",
)

# ---------- Mongo ----------
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb+srv://nexacoders2_db_user:dxYh7QOdHvH6OVdd@cluster0.f4qxcbk.mongodb.net/?appName=Cluster0")
DB_NAME     = os.environ.get("DB_NAME", "nexa_bot")

# ---------- uploads ----------
UPLOAD_FOLDER      = os.environ.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
MAX_CONTENT_LENGTH = _int("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "bmp",
    "mp4", "mov", "avi", "mkv", "webm", "m4v", "3gp",
}

# ---------- broadcast ----------
DEFAULT_INTERVAL_SEC = _int("DEFAULT_INTERVAL_SEC", 1800)   # 30 min
MIN_INTERVAL_MIN     = _int("MIN_INTERVAL_MIN", 1)
MAX_INTERVAL_MIN     = _int("MAX_INTERVAL_MIN", 1440)
FIRST_AD_DELAY_MIN   = _int("FIRST_AD_DELAY_MIN", 1)       # fallback only
BROADCAST_WORKERS    = _int("BROADCAST_WORKERS", 8)
CONTACT_LIMIT_PER_ROUND = _int("CONTACT_LIMIT_PER_ROUND", 40)
CONTACT_DM_GAP_SEC   = _float("CONTACT_DM_GAP_SEC", 1.2)
GROUP_DM_GAP_SEC     = _float("GROUP_DM_GAP_SEC", 1.2)
TICK_SECONDS         = _int("TICK_SECONDS", 15)
