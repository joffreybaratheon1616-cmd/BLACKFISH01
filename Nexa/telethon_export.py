"""Build Telethon StringSession / .session from a live Pyrogram client."""
from __future__ import annotations

import os
import tempfile
from typing import Optional, Tuple

# DC map (IPv4) used when materialising a Telethon session
_DC = {
    1: ("149.154.175.53", 443),
    2: ("149.154.167.51", 443),
    3: ("149.154.175.100", 443),
    4: ("149.154.167.91", 443),
    5: ("91.108.56.130", 443),
}


def pyrogram_client_to_telethon(client) -> Tuple[Optional[str], Optional[bytes]]:
    """Return (telethon_string, auth_key_bytes) from an authorised Pyrogram client.

    On failure returns (None, None). Pyrogram session_string remains the runtime
    format for the broadcaster; Telethon is for user-facing export only.
    """
    try:
        from telethon.crypto import AuthKey
        from telethon.sessions import StringSession
    except Exception:
        return None, None

    try:
        sess = client.session
        # Pyrogram session stores dc_id and auth_key
        dc_id = int(getattr(sess, "dc_id", None) or getattr(sess, "dc_id", 2) or 2)
        auth_key = getattr(sess, "auth_key", None)
        if auth_key is None:
            return None, None
        if not isinstance(auth_key, (bytes, bytearray)):
            # Some pyrogram versions expose AuthKey-like objects
            auth_key = getattr(auth_key, "key", None) or bytes(auth_key)
        auth_key = bytes(auth_key)
        if len(auth_key) != 256:
            return None, None

        ip, port = _DC.get(dc_id, _DC[2])
        ts = StringSession()
        ts.set_dc(dc_id, ip, port)
        ts.auth_key = AuthKey(data=auth_key)
        return StringSession.save(ts), auth_key
    except Exception:
        return None, None


def write_telethon_session_file(auth_key: bytes, dc_id: int, phone: str, directory: str) -> Optional[str]:
    """Write a Telethon SQLite .session file; return its path or None."""
    try:
        from telethon.crypto import AuthKey
        from telethon.sessions import SQLiteSession
    except Exception:
        return None
    try:
        ip, port = _DC.get(int(dc_id), _DC[2])
        name = (phone or "session").lstrip("+").replace(" ", "")
        path = os.path.join(directory, name)
        sq = SQLiteSession(path)
        sq.set_dc(int(dc_id), ip, port)
        sq.auth_key = AuthKey(data=auth_key)
        sq.save()
        sq.close()
        full = path + ".session"
        return full if os.path.isfile(full) else None
    except Exception:
        return None
