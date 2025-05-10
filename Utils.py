import os
import re
import logging
import tempfile

from telegram import Update, Message, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

import pytesseract
from PIL import Image
import aiohttp

import whisper
import moviepy.editor as mp
import speech_recognition as sr

# Initialize Whisper model
whisper_model = whisper.load_model("base")

# Homework keywords
HOMEWORK_KEYWORDS = [
    "homework", "question", "worksheet", "exercise", "page",
    "complete", "write", "read", "submit", "draw", "copy", "do"
]

# Junk patterns
JUNK_PATTERNS = [
    r"(?i)/\w+bot@", r"(http|www\.)", r"free proxy", r"vpn", r"promo", r"subscribe"
]

# Check if message is junk
def is_junk_message(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in JUNK_PATTERNS)

# Check if message is homework
def is_homework(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in HOMEWORK_KEYWORDS)

# Get forwarded parent group ID
def get_parent_group_id(student_chat_id: int, bot_data) -> int | None:
    routes = bot_data.get("ROUTES")
    if not routes:
        return None
    try:
        route_map = {int(k): int(v) for k, v in [pair.split(":") for pair in routes.split(",")]}
        return route_map.get(student_chat_id)
    except Exception as e:
        logging.error(f"Error parsing ROUTES: {e}")
        return None

# OCR text from Telegram image
async def extract_text_from_image(message: Message) -> str:
    if not message.photo:
        return ""
    try:
        photo_file = await message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as img_file:
            await photo_file.download_to_drive(img_file.name)
            image = Image.open(img_file.name)
            text = pytesseract.image_to_string(image)
            return text.strip()
    except Exception as e:
        logging.warning(f"OCR failed: {e}")
        return ""

# Convert voice/audio/video to text using Whisper
async def extract_text_from_audio(update: Update, message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
    audio_file = None
    ext = "ogg"

    try:
        file = await message.voice.get_file() if message.voice else \
               await message.audio.get_file() if message.audio else \
               await message.video.get_file()

        if message.audio:
            ext = message.audio.file_name.split('.')[-1]
        elif message.video:
            ext = "mp4"

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as temp:
            await file.download_to_drive(temp.name)
            audio_file = temp.name

        # Convert to WAV if needed (for fallback)
        audio_path = audio_file
        if ext in ("mp4", "mov"):
            video = mp.VideoFileClip(audio_path)
            wav_path = audio_path.replace(f".{ext}", ".wav")
            video.audio.write_audiofile(wav_path, codec='pcm_s16le')
            audio_path = wav_path

        # Use Whisper
        result = whisper_model.transcribe(audio_path)
        return result.get("text", "").strip()

    except Exception as e:
        logging.warning(f"Whisper transcription failed: {e}")

        # Try fallback using Google SpeechRecognition
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio_data = r.record(source)
                text = r.recognize_google(audio_data)
                return text
        except Exception as e2:
            logging.error(f"Google STT fallback failed: {e2}")
            return ""

# Forward to parent group
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    student_chat_id = message.chat_id
    parent_chat_id = get_parent_group_id(student_chat_id, context.bot_data)

    if not parent_chat_id:
        logging.info(f"No route found for {student_chat_id}")
        return

    try:
        await message.copy(chat_id=parent_chat_id)
        logging.info(f"Forwarded message from {student_chat_id} to {parent_chat_id}")
    except Exception as e:
        logging.warning(f"Failed to forward: {e}")

# Admin check
def is_admin(user_id: int, bot_data) -> bool:
    return user_id in bot_data.get("ADMIN_CHAT_IDS", set())