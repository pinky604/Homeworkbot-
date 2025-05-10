import whisper
import pytesseract
from PIL import Image
import io
from telegram import Update
from telegram.ext import ContextTypes

# Load Whisper model for audio processing
whisper_model = whisper.load_model("base")  # You can choose a different model size like "small", "medium", or "large"

# Function to transcribe audio (voice messages, audio files)
async def download_and_transcribe_audio(file):
    # Download the audio file as a bytearray
    audio = await file.download_as_bytearray()
    
    # Process the audio using Whisper
    result = whisper_model.transcribe(io.BytesIO(audio))
    
    # Return transcribed text
    return result['text']

# Function to extract text from images using OCR (Tesseract)
def extract_text_from_image(image_bytes):
    # Open image using Pillow
    image = Image.open(io.BytesIO(image_bytes))
    
    # Use pytesseract to extract text from the image
    text = pytesseract.image_to_string(image)
    
    # Return extracted text
    return text

# Function to check if the extracted text contains homework-related keywords
def is_homework_text(text):
    # Define keywords associated with homework
    homework_keywords = [
        "write", "read", "draw", "page", "complete", "question", 
        "homework", "exercise", "submit", "copy", "worksheet"
    ]
    
    # Scan through the text and check for the presence of any homework-related keywords
    for keyword in homework_keywords:
        if keyword in text.lower():
            return True
    return False

# Function to handle image processing and homework forwarding
async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    # If the message contains an image (photo)
    if message.photo:
        await message.chat.send_action("upload_photo")
        file = await message.photo[-1].get_file()  # Get the largest resolution photo
        image_bytes = await file.download_as_bytearray()
        
        # Extract text from image using OCR
        extracted_text = extract_text_from_image(image_bytes)
        
        if is_homework_text(extracted_text):
            # Forward the message to the parent group (example)
            await forward_homework_message(update, extracted_text)

    # If the message contains audio or voice (voice message or audio file)
    elif message.voice or message.audio:
        await message.chat.send_action("record_audio")
        file = await (message.voice or message.audio).get_file()
        
        # Transcribe the audio using Whisper
        transcribed_text = await download_and_transcribe_audio(file)
        
        if is_homework_text(transcribed_text):
            # Forward the transcribed homework message to the parent group (example)
            await forward_homework_message(update, transcribed_text)

# Example function for forwarding the message to a parent group
async def forward_homework_message(update: Update, homework_text: str):
    # Forward the message to the parent group (you can replace with actual group ID)
    parent_group_chat_id = "YOUR_PARENT_GROUP_CHAT_ID"  # Replace with your parent group chat ID
    await update.message.reply_text(f"Homework received: {homework_text}")
    await context.bot.send_message(chat_id=parent_group_chat_id, text=f"Homework Alert: {homework_text}")