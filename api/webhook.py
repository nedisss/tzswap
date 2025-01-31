from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import requests
import datetime
import telebot  # Naudojame sinchroninį TeleBot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Užkrauname aplinkos kintamuosius iš .env failo
load_dotenv()

# API tokenas
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Naudojame kintamąjį iš .env failo
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set correctly.")
bot = telebot.TeleBot(BOT_TOKEN)  # Sinchroninis TeleBot

# Firebase inicializavimas
firebase_config = os.getenv('FIREBASE_SERVICE_ACCOUNT')
if not firebase_config:
    raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable is not set correctly.")
firebase_config = json.loads(firebase_config)
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {'storageBucket': 'tswap-c0f2c.appspot.com'})
db = firestore.client()
bucket = storage.bucket()

# Naudotojo paveikslėlio įkėlimas
def upload_user_image(user_id, file_url):
    response = requests.get(file_url)
    if response.status_code == 200:
        image_data = response.content
        blob = bucket.blob(f"user_images/{user_id}.jpg")
        blob.upload_from_string(image_data, content_type='image/jpeg')
        return blob.generate_signed_url(datetime.timedelta(days=365), method='GET')
    return None

# Webhook POST užklausos apdorojimas
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update_dict = json.loads(post_data.decode('utf-8'))
        self.process_update(update_dict)
        self.send_response(200)
        self.end_headers()

    def process_update(self, update_dict):
        update = types.Update.de_json(update_dict)
        bot.process_new_updates([update])

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

# Komandos handleris /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    user_first_name = str(message.from_user.first_name)
    user_last_name = message.from_user.last_name
    user_username = message.from_user.username
    user_language_code = str(message.from_user.language_code)
    is_premium = message.from_user.is_premium
    text = message.text.split()

    welcome_message = (
        f"Hi, {user_first_name}!\U0001F44B\n\n"
        f"Welcome to tswap!\U0001F389\n\n"
        f"Here you can earn coins by mining them!\n\n"
        f"Invite friends to earn more coins together, and level up faster!\U0001F680"
    )

    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        user_image = None

        if not user_doc.exists:
            photos = bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                file_info = bot.get_file(file_id)
                file_path = file_info.file_path
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                user_image = upload_user_image(user_id, file_url)

        user_data = {
            'userImage': user_image,
            'firstName': user_first_name,
            'lastName': user_last_name,
            'username': user_username,
            'languageCode': user_language_code,
            'isPremium': is_premium,
            'referrals': {},
            'balance': 0,
            'mineRate': 0.001,
            'isMining': False,
            'miningStartedTime': None,
            'daily': {
                'claimedTime': None,
                'claimedDay': 0,
            },
            'links': None,
            'referredBy': None
        }

        if len(text) > 1 and text[1].startswith('ref_'):
            referrer_id = text[1][4:]
            referrer_ref = db.collection('users').document(referrer_id)
            referrer_doc = referrer_ref.get()

            if referrer_doc.exists:
                user_data['referredBy'] = referrer_id
                referrer_data = referrer_doc.to_dict()

                bonus_amount = 500 if is_premium else 100
                new_balance = referrer_data.get('balance', 0) + bonus_amount
                referrals = referrer_data.get('referrals', {}) or {}
                referrals[user_id] = {
                    'addedValue': bonus_amount,
                    'firstName': user_first_name,
                    'lastName': user_last_name,
                    'userImage': user_image,
                }

                referrer_ref.update({
                    'balance': new_balance,
                    'referrals': referrals
                })

        user_ref.set(user_data)
        keyboard = generate_start_keyboard()
        bot.reply_to(message, welcome_message, reply_markup=keyboard)

    except Exception as e:
        error_message = "Error. Please try again!"
        bot.reply_to(message, error_message)
        print(f"Error: {str(e)}")

# Klaviatūros mygtukas
def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Open Tswap App", web_app=WebAppInfo(url="https://tzswap.netlify.app/")))
    return keyboard

# Serverio paleidimas
def run(server_class=HTTPServer, handler_class=WebhookHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting server on port {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
