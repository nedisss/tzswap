import json
import os
import requests
import datetime
import telebot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv
from aiohttp import web

# Įkeliame aplinkos kintamuosius
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set correctly.")
bot = telebot.TeleBot(BOT_TOKEN)

firebase_config = os.getenv('FIREBASE_SERVICE_ACCOUNT')
if not firebase_config:
    raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable is not set correctly.")
try:
    firebase_config = json.loads(firebase_config)
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred, {'storageBucket': 'tswap-c0f2c.appspot.com'})
    db = firestore.client()
    bucket = storage.bucket()
except Exception as e:
    raise ValueError(f"Firebase initialization failed: {e}")

# Pagalbinė funkcija vartotojo paveikslėlio įkėlimui į Firebase
def upload_user_image(user_id, file_url):
    try:
        response = requests.get(file_url)
        if response.status_code == 200:
            image_data = response.content
            blob = bucket.blob(f"user_images/{user_id}.jpg")
            blob.upload_from_string(image_data, content_type='image/jpeg')
            return blob.generate_signed_url(datetime.timedelta(days=365), method='GET')
    except Exception as e:
        print(f"Image upload failed: {e}")
    return None

# Webhook endpointas, kuriam siunčiami Telegram atnaujinimai
async def webhook(request):
    try:
        update_dict = await request.json()  # gauti užklausą
        update = types.Update.de_json(update_dict)  # apdoroti atnaujinimą
        bot.process_new_updates([update])  # siųsti naujus atnaujinimus į botą
        return web.json_response({"status": "success"}), 200
    except Exception as e:
        print(f"Error processing update: {e}")
        return web.json_response({"status": "error", "message": str(e)}), 500

# Pagrindinis kelias, kuris tikrina serverio būseną
async def health_check(request):
    return web.Response(text="Bot is running", status=200)

# Startuoti aiohttp serverį
app = web.Application()
app.router.add_post('/webhook', webhook)  # Webhook endpointas
app.router.add_get('/', health_check)    # Pagrindinis kelias

# Jei naudojate Vercel, nereikia šio kodo, bet vietiniam serveriui galima įdėti:
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
