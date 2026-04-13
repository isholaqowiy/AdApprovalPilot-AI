import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "BlockSavvyMx"
# Using /tmp ensures Render has permission to write the database
DB_PATH = "/tmp/users.db"

app = Flask(__name__)

# Initialize DB properly
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, status TEXT)')
    conn.commit()
    conn.close()

# Initialize PTB Application
ptb_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🔑 Admin Access", callback_data="req_access")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🚀 **AdApprovalPilotAI Bot Live**\n\nRequest access to start.", reply_markup=reply_markup, parse_mode='Markdown')

# Webhook Route
@app.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    # We use a helper to run the async PTB processing
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    # This runs the async processing in the current event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ptb_app.process_update(update))
    return "OK", 200

@app.route("/", methods=['GET'])
def index():
    return "Bot is running", 200

# PTB Setup
async def setup():
    ptb_app.add_handler(CommandHandler("start", start))
    # Add other handlers here as needed
    await ptb_app.initialize()

# Run setup
init_db()
asyncio.run(setup())

if __name__ == "__main__":
    app.run(port=10000)
