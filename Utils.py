import os 
import re 
import aiohttp 
import tempfile 
import whisper 
from PIL import Image 
from io import BytesIO 
from pytesseract import image_to_string 
from telegram import Message 
from telegram.files.file import File

def is_junk_message(message: Message) -> bool: text = message.text or message.caption or "" return bool(re.search(r"/(?:@|https?:|www.|shopbot|click here|vpn)", text.lower()))

def extract_text_from_image(image_bytes: bytes) -> str: try: image = Image.open(BytesIO(image_bytes)) return image_to_string(image) except Exception: return ""

async def download_and_transcribe_audio(file: File) -> str: with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp: await file.download_to_drive(custom_path=temp.name) try: model = whisper.load_model("base") result = model.transcribe(temp.name) return result.get("text", "") except Exception: return ""

def parse_routes_from_env(): route_str = os.getenv("ROUTES_MAP", "") routes = {} for pair in route_str.split(","): if ":" in pair: from_id, to_id = pair.split(":") routes[int(from_id.strip())] = [int(tid) for tid in to_id.split("+")] return routes

def extract_keywords(text: str): return re.findall(r"\b\w{4,}\b", text.lower())

def is_admin(user): admin_ids = os.getenv("ADMIN_IDS", "").split(",") return str(user.id) in admin_ids

