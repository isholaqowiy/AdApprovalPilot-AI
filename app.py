import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://adapprovalpilot-ai-sgdc.onrender.com
ADMIN_USERNAME = "BlockSavvyMx"
DB_PATH = "/tmp/users.db"

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, status TEXT)')
    conn.commit()
    conn.close()

ptb_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🔑 Admin Access", callback_data="req_access")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚀 **AdApprovalPilotAI Bot Live**\n\nRequest access to start.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

@app.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    # Reuse the existing event loop instead of creating a new one
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ptb_app.process_update(update))
    return "OK", 200

@app.route("/", methods=['GET'])
def index():
    return "Bot is running", 200

async def setup():
    ptb_app.add_handler(CommandHandler("start", start))
    await ptb_app.initialize()
    # ✅ Register the webhook with Telegram
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
    logger.info(f"Webhook set to {WEBHOOK_URL}/{TOKEN}")

init_db()
asyncio.run(setup())

if __name__ == "__main__":
    app.run(port=10000)
