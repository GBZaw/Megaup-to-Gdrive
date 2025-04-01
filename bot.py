import os
import urllib.parse
import requests
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler
from telegram.ext import filters
from aiohttp import web

# Telegram Bot Token ကို environment variable ကနေ ဖတ်ပါမယ်
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_URL = os.getenv("RAILWAY_URL")

# Bot ကို ဖန်တီးပါ
app = Application.builder().token(BOT_TOKEN).build()

# Start command handler
async def start(update, context):
    await update.message.reply_text("Hello! Please send me a MegaUp direct download link, and I'll download it to your local storage.")

# Message handler to process MegaUp links
async def handle_message(update, context):
    message_text = update.message.text

    # Check if the message is a URL
    if "megaup.net" in message_text:
        await update.message.reply_text("Received your MegaUp link! Downloading...")

        # Extract the original file name from the URL
        parsed_url = urllib.parse.urlparse(message_text)
        file_name = os.path.basename(parsed_url.path)
        file_name = urllib.parse.unquote(file_name)

        # Define the path where the file will be saved (local storage)
        save_path = f"./downloads/{file_name}"

        # Create the downloads folder if it doesn't exist
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Download the file
        try:
            os.system(f'wget -O "{save_path}" "{message_text}"')
            if os.path.exists(save_path):
                await update.message.reply_text(f"File downloaded successfully: {file_name}")
            else:
                await update.message.reply_text("Download failed: File not found.")
        except Exception as e:
            await update.message.reply_text(f"Error occurred: {str(e)}")
    else:
        await update.message.reply_text("Please send a valid MegaUp direct download link.")

# Add handlers to the application
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Text() & ~filters.Command(), handle_message))

# Webhook handler for Railway.app
async def webhook(request):
    try:
        update = telegram.Update.de_json(await request.json(), app.bot)
        if update:
            await app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        print(f"Error in webhook: {str(e)}")
        return web.Response(text="Error", status=500)

# Set up the webhook server
async def main():
    # Set webhook
    webhook_url = f"{RAILWAY_URL}/{BOT_TOKEN}"
    await app.bot.set_webhook(url=webhook_url)
    print(f"Webhook set to: {webhook_url}")

    # Start the webhook server
    port = int(os.getenv("PORT", 8080))  # Railway.app မှာ PORT ကို သတ်မှတ်ထားရင် အဲဒီ port ကို သုံးမယ်
    web_app = web.Application()
    web_app.router.add_post(f"/{BOT_TOKEN}", webhook)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Bot is running with webhook on port {port}...")

    # Keep the application running
    await app.initialize()
    await app.start()
    # Run forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
