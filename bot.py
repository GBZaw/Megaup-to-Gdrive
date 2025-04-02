import os
import json
import subprocess
from flask import Flask, request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Flask app ဖန်တီးပါ
app = Flask(__name__)

# Google Drive API အတွက် SCOPES
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Telegram Bot Token ကို environment variable ကနေ ဖတ်ပါ
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_URL = os.getenv("RAILWAY_URL")

# Telegram Bot နဲ့ Updater ဖန်တီးပါ
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Google Drive API ကို အသုံးပြုဖို့ service ဖန်တီးပါ
def get_drive_service():
    creds = None
    # Environment variables ကနေ credentials နဲ့ token ကို ဖတ်ပါ
    credentials_json = os.getenv("CREDENTIALS_JSON")
    token_json = os.getenv("TOKEN_JSON")

    # credentials.json ကို ဖတ်ပါ
    credentials_dict = json.loads(credentials_json)

    # token.json ကို ဖတ်ပါ
    if token_json:
        token_dict = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_dict, SCOPES)

    # အကယ်၍ credentials မရှိရင် ဒါမှမဟုတ် မမှန်ကန်ရင် အသစ်ဖန်တီးပါ
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(credentials_dict, SCOPES)
        creds = flow.run_local_server(port=0)
        # ဖန်တီးထားတဲ့ credentials ကို environment variable ထဲ ပြန်သိမ်းပါ
        os.environ["TOKEN_JSON"] = json.dumps({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
            "expiry": creds.expiry.isoformat()
        })

    return build('drive', 'v3', credentials=creds)

# MegaUp လင့်ခ်ကနေ ဖိုင်ကို ဒေါင်းလုဒ်လုပ်ပါ
def download_file(url, file_name):
    download_path = f"./downloads/{file_name}"
    # ဖိုင်ရှိမရှိ စစ်ဆေးပါ
    if os.path.exists(download_path):
        print(f"File {file_name} already exists, skipping download.")
        return download_path
    # ဖိုင်မရှိရင် ဒေါင်းလုဒ်လုပ်ပါ
    subprocess.run(["wget", url, "-O", download_path])
    return download_path

# Google Drive ထဲ ဖိုင်ကို အပ်လုဒ်လုပ်ပါ
def upload_to_drive(file_path, file_name):
    try:
        service = get_drive_service()
        file_metadata = {'name': file_name}
        media = MediaFileUpload(file_path, resumable=True)
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        file_id = response.get('id')
        print(f"File uploaded to Google Drive with ID: {file_id}")

        # ဖိုင်ကို မျှဝေလို့ရအောင် လုပ်ပါ
        service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'},
            fields='id'
        ).execute()

        # Google Drive လင့်ခ်ကို ပြန်ပေးပါ
        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception as e:
        print(f"Error uploading to Google Drive: {str(e)}")
        return None

# /start command အတွက် handler
def start(update, context):
    update.message.reply_text("Hello! I am a bot that can download files from MegaUp links and upload them to Google Drive. Just send me a MegaUp direct download link.")

# MegaUp လင့်ခ်ကို လက်ခံပြီး လုပ်ဆောင်မယ့် handler
def handle_message(update, context):
    message = update.message.text
    if "megaup.net" in message:
        update.message.reply_text("Downloading the file, please wait...")
        try:
            # ဖိုင်နာမည်ကို လင့်ခ်ကနေ ထုတ်ယူပါ
            file_name = message.split("/")[-1].split("?")[0]
            # ဖိုင်ကို ဒေါင်းလုဒ်လုပ်ပါ
            file_path = download_file(message, file_name)
            update.message.reply_text("File downloaded successfully! Uploading to Google Drive...")
            # Google Drive ထဲ အပ်လုဒ်လုပ်ပါ
            drive_link = upload_to_drive(file_path, file_name)
            if drive_link:
                update.message.reply_text(f"File uploaded to Google Drive: {drive_link}")
            else:
                update.message.reply_text("Failed to upload to Google Drive.")
            # ဒေါင်းလုဒ်လုပ်ထားတဲ့ ဖိုင်ကို ဖျက်ပါ
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            update.message.reply_text(f"Error: {str(e)}")
    else:
        update.message.reply_text("Please send a valid MegaUp direct download link.")

# Flask route ဖန်တီးပါ
@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK", 200

# Webhook ကို သတ်မှတ်ပါ
def set_webhook():
    webhook_url = f"{RAILWAY_URL}/{TELEGRAM_BOT_TOKEN}"
    bot.setWebhook(webhook_url)
    print(f"Webhook set to: {webhook_url}")

# Command နဲ့ Message handler တွေကို ထည့်ပါ
start_handler = CommandHandler('start', start)
message_handler = MessageHandler(Filters.text & ~Filters.command, handle_message)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(message_handler)

# Flask app ကို run ပါ
if __name__ == "__main__":
    # downloads ဖိုလ်ဒါ ဖန်တီးပါ
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    # Webhook ကို သတ်မှတ်ပါ
    set_webhook()
    # Flask app ကို run ပါ
    port = int(os.getenv("PORT", 8080))
    print(f"Bot is running with webhook on port {port}...")
    app.run(host="0.0.0.0", port=port)
