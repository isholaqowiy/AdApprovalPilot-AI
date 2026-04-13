import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from database import init_db, get_user_status, update_user_status

# Logging
logging.basicConfig(level=logging.INFO)

# --- CONFIGURATION ---
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # e.g. https://your-app.onrender.com
ADMIN_USERNAME = "BlockSavvyMx" 
# Note: In production, it's safer to use ADMIN_ID (integer) if known.

# Conversation States
CHANNEL, GROUP, BOT_LINK, AD_TEXT, BUDGET, CPM = range(6)

app = Flask(__name__)
# Initialize Bot Application
ptb_app = Application.builder().token(TOKEN).build()

# --- HELPER: ACCESS CHECK ---
def is_approved(user_id):
    return get_user_status(user_id) == 'approved'

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 **Welcome to AdApprovalPilotAI Bot**\n\n"
        "We help you resolve Telegram Ad issues:\n"
        "• Destination Quality rejection\n"
        "• Ads stuck in review\n"
        "• Low CPM optimization\n\n"
        "⚠️ *Note: You must request Admin Access before using tools.*"
    )
    keyboard = [
        [InlineKeyboardButton("🔑 Admin Access", callback_data="req_access")],
        [InlineKeyboardButton("📊 Channel Index", callback_data="btn_channel"),
         InlineKeyboardButton("👥 Group Index", callback_data="btn_group")],
        [InlineKeyboardButton("🤖 Bot Index", callback_data="btn_bot"),
         InlineKeyboardButton("✍️ Ad Text Analyzer", callback_data="btn_adtext")],
        [InlineKeyboardButton("💰 Ad Budget", callback_data="btn_budget"),
         InlineKeyboardButton("📈 Ad CPM", callback_data="btn_cpm")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# --- HANDLERS ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data == "req_access":
        update_user_status(user.id, user.username, "pending")
        # Notify Admin
        admin_msg = (
            f"🔔 **New Access Request**\n"
            f"ID: `{user.id}`\n"
            f"User: @{user.username}\n"
            f"Name: {user.first_name}"
        )
        admin_kb = [
            [InlineKeyboardButton("✅ Accept", callback_data=f"adm_acc_{user.id}"),
             InlineKeyboardButton("❌ Deny", callback_data=f"adm_den_{user.id}")]
        ]
        # In a real scenario, you'd need the Admin's Chat ID. 
        # For this logic, we assume the admin interacts with the bot.
        await context.bot.send_message(chat_id=f"@{ADMIN_USERNAME}", text=admin_msg, reply_markup=InlineKeyboardMarkup(admin_kb), parse_mode='Markdown')
        await query.edit_message_text("Request sent to Admin. Please wait for approval.")
        return

    # Admin actions (Accept/Deny)
    if data.startswith("adm_"):
        if user.username != ADMIN_USERNAME:
            return
        
        action, _, target_id = data.split("_")[1:]
        target_id = int(target_id)
        
        if action == "acc":
            update_user_status(target_id, "", "approved")
            await context.bot.send_message(chat_id=target_id, text="✅ Admin Access Granted! You can now use all features.")
            await query.edit_message_text(f"User {target_id} approved.")
        else:
            update_user_status(target_id, "", "denied")
            await context.bot.send_message(chat_id=target_id, text="❌ Your Admin Access request was denied.")
            await query.edit_message_text(f"User {target_id} denied.")
        return

    # Check approval for all other buttons
    if not is_approved(user.id):
        await query.message.reply_text("🚫 You need admin approval first. Click **Admin Access**.", parse_mode='Markdown')
        return

    # Trigger Conversation flows
    if data == "btn_channel":
        await query.message.reply_text("Please send the link to your Telegram Channel:")
        return CHANNEL
    elif data == "btn_group":
        await query.message.reply_text("Please send the link to your Telegram Group:")
        return GROUP
    # ... Add logic for other buttons similarly

# --- ANALYSIS HANDLERS ---
async def analyze_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    response = (
        f"🔍 **Analysis for {link}**\n\n"
        "• **Channel Name**: Good\n"
        "• **Description**: Needs more keywords related to your niche.\n"
        "• **Activity**: Suggest posting 2x daily to improve quality score.\n\n"
        "✅ **Status**: Good"
    )
    await update.message.reply_text(response, parse_mode='Markdown')
    return ConversationHandler.END

async def analyze_ad_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    risk = "High" if any(word in text.lower() for word in ["earn fast", "guarantee", "crypto lucky"]) else "Low"
    response = (
        f"✍️ **Ad Text Analysis**\n\n"
        f"🚩 **Risk Level**: {risk}\n"
        f"💡 **Suggestion**: Avoid superlative claims. Use 'Discover' instead of 'Guarantee'."
    )
    await update.message.reply_text(response, parse_mode='Markdown')
    return ConversationHandler.END

# --- WEBHOOK ROUTE ---
@app.route(f"/{TOKEN}", methods=['POST'])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), ptb_app.bot)
        await ptb_app.process_update(update)
        return "OK", 200

@app.route("/", methods=['GET'])
def index():
    return "Bot is running", 200

# --- APP RUNNER ---
def setup_handlers():
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback)],
        states={
            CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_channel)],
            AD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_ad_text)],
            # Add other states here...
        },
        fallbacks=[CommandHandler("start", start)],
    )
    ptb_app.add_handler(conv_handler)
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CallbackQueryHandler(button_callback)) # Handle non-conv buttons

if __name__ == "__main__":
    init_db()
    setup_handlers()
    # On Render, we usually use Gunicorn to run the app, 
    # but for local testing:
    # app.run(port=8000)
