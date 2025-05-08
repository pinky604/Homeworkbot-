import io
import re
import pytz
import datetime
from PIL import Image
from pytesseract import image_to_string
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes
from utils import (
    is_junk_message,
    extract_text_from_image,
    download_and_transcribe_audio,
    parse_routes_from_env,
)

BT_TZ = pytz.timezone("Asia/Thimphu")
HOMEWORK_KEYWORDS = {
    "homework", "hw", "assignment", "work", "activity", "task",
    "write", "read", "draw", "page", "complete", "question", "exercise", "submit", "copy", "worksheet"
}

ROUTES = parse_routes_from_env()

ADMIN_IDS = {123456789}  # Replace with actual admin user IDs

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        now = datetime.datetime.now(BT_TZ)
        hour = now.hour
        weekday = now.strftime("%A")

        if hour < 12:
            time_emoji = "☀️"
            greeting = "Good morning"
        elif hour < 17:
            time_emoji = "🌤️"
            greeting = "Good afternoon"
        elif hour < 21:
            time_emoji = "🌙"
            greeting = "Good evening"
        else:
            time_emoji = "🌌"
            greeting = "Good night"

        weekday_emoji = {
            "Monday": "✨",
            "Friday": "🎉",
            "Saturday": "😎",
            "Sunday": "🧘‍♀️",
        }.get(weekday, "📚")

        await update.message.reply_text(
            f"{time_emoji} {greeting}, teacher!\n\nI'm the Homework Forwarder Bot. {weekday_emoji}"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now(BT_TZ).strftime('%Y-%m-%d %H:%M:%S')
    route_count = len(ROUTES)
    await update.message.reply_text(
        f"✅ Bot is online!\n\n⏰ Time: {now}\n🧭 Mapped groups: {route_count}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in ADMIN_IDS
    if is_admin:
        help_text = (
            "🛠️ *Admin Commands:*\n"
            "/reload_config - Reload routing config\n"
            "/weekly_summary - Show homework log summary\n"
            "/clear_homework_log - Clear weekly homework log\n"
            "/list_senders - View recent sender activity\n"
            "/clear_senders - Clear sender activity\n"
            "/id - Get chat/user ID info"
        )
    else:
        help_text = (
            "🧾 *User Help:*\n"
            "/start - Greet the bot\n"
            "/status - Check bot status\n"
            "/id - Get your ID\n"
            "/help - Show this message"
        )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    await update.message.reply_text(f"👤 User ID: `{user_id}`\n💬 Chat ID: `{chat_id}`", parse_mode=ParseMode.MARKDOWN)

def is_homework_text(text: str) -> bool:
    if not text:
        return False
    text = text.lower()
    return any(word in text for word in HOMEWORK_KEYWORDS)

async def forward_to_parents(context: ContextTypes.DEFAULT_TYPE, parent_ids, message):
    for parent_id in parent_ids:
        try:
            await message.copy(chat_id=parent_id)
        except Exception as e:
            print(f"Failed to forward to {parent_id}: {e}")

async def log_sender_activity(context: ContextTypes.DEFAULT_TYPE, user, message_text):
    bot_data = context.bot_data.setdefault("SENDER_ACTIVITY", {})
    bot_data[user.id] = {
        "name": user.full_name,
        "last_message": message_text[:100],
        "timestamp": datetime.datetime.now(BT_TZ).isoformat()
    }

async def log_forwarded_message(context: ContextTypes.DEFAULT_TYPE, chat_id, message_text):
    logs = context.bot_data.setdefault("FORWARDED_LOGS", [])
    logs.append({
        "group_id": chat_id,
        "message": message_text[:100],
        "timestamp": datetime.datetime.now(BT_TZ).isoformat()
    })

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id

    if chat_id not in ROUTES:
        return

    if is_junk_message(message):
        return

    matched = False
    extracted_text = ""

    if message.text or message.caption:
        text = message.text or message.caption
        if is_homework_text(text):
            matched = True
            extracted_text = text

    elif message.photo:
        await message.chat.send_action(ChatAction.UPLOAD_PHOTO)
        file = await message.photo[-1].get_file()
        image_bytes = await file.download_as_bytearray()
        text = extract_text_from_image(image_bytes)
        if is_homework_text(text):
            matched = True
            extracted_text = text

    elif message.voice or message.audio:
        await message.chat.send_action(ChatAction.RECORD_AUDIO)
        file = await (message.voice or message.audio).get_file()
        transcribed_text = await download_and_transcribe_audio(file)
        if is_homework_text(transcribed_text):
            matched = True
            extracted_text = transcribed_text

    if matched:
        parent_ids = ROUTES[chat_id]
        await forward_to_parents(context, parent_ids, message)
        await log_sender_activity(context, user, extracted_text)
        await log_forwarded_message(context, chat_id, extracted_text)

async def reload_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ROUTES
    ROUTES = parse_routes_from_env()
    await update.message.reply_text("🔄 Configuration reloaded from .env!")

async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logs = context.bot_data.get("FORWARDED_LOGS", [])
    now = datetime.datetime.now(BT_TZ)
    one_week_ago = now - datetime.timedelta(days=7)

    filtered_logs = [
        log for log in logs
        if datetime.datetime.fromisoformat(log["timestamp"]) > one_week_ago
    ]

    summary = {}
    for log in filtered_logs:
        group_id = log["group_id"]
        summary[group_id] = summary.get(group_id, 0) + 1

    if not summary:
        await update.message.reply_text("😐 No homework messages were forwarded in the past 7 days.")
        return

    summary_lines = [f"📘 Group {gid}: {count} messages" for gid, count in summary.items()]
    summary_text = "\n".join(summary_lines)
    await update.message.reply_text(f"📊 *Weekly Homework Summary:*\n\n{summary_text}", parse_mode=ParseMode.MARKDOWN)

async def clear_homework_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data["FORWARDED_LOGS"] = []
    await update.message.reply_text("🗑️ Homework log cleared.")

async def list_senders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    senders = context.bot_data.get("SENDER_ACTIVITY", {})
    if not senders:
        await update.message.reply_text("😶 No recent sender activity.")
        return

    lines = []
    for uid, data in senders.items():
        lines.append(f"👤 {data['name']} ({uid})\n🕒 {data['timestamp']}\n✏️ {data['last_message']}\n")

    await update.message.reply_text("\n\n".join(lines))

async def clear_senders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data["SENDER_ACTIVITY"] = {}
    await update.message.reply_text("🧹 Cleared sender activity log.")
  
