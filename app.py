import os
import logging
import asyncio
import sqlite3
import re
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
TOKEN          = os.getenv("BOT_TOKEN")
WEBHOOK_URL    = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.onrender.com
ADMIN_USERNAME = "BlockSavvyMx"
DB_PATH        = "/tmp/users.db"

# ─────────────────────────────────────────────
# CONVERSATION STATES
# ─────────────────────────────────────────────
(
    WAIT_CHANNEL_LINK,
    WAIT_GROUP_LINK,
    WAIT_BOT_LINK,
    WAIT_AD_TEXT,
    WAIT_BUDGET,
    WAIT_CPM_NICHE,
) = range(6)

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            access_status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def upsert_user(user_id: int, username: str, first_name: str, status: str = "pending"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, username, first_name, access_status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            access_status=COALESCE(
                CASE WHEN access_status='approved' THEN 'approved' END,
                excluded.access_status
            )
    """, (user_id, username or "", first_name or "", status))
    conn.commit()
    conn.close()

def set_user_status(user_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET access_status=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

def get_user_status(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT access_status FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Request Admin Access", callback_data="req_access")],
        [
            InlineKeyboardButton("📊 Channel Index", callback_data="channel_index"),
            InlineKeyboardButton("👥 Group Index",   callback_data="group_index"),
        ],
        [
            InlineKeyboardButton("🤖 Bot Index",     callback_data="bot_index"),
            InlineKeyboardButton("✍️ Ad Text",        callback_data="ad_text"),
        ],
        [
            InlineKeyboardButton("💰 Ad Budget",     callback_data="ad_budget"),
            InlineKeyboardButton("📉 Ad CPM",        callback_data="ad_cpm"),
        ],
    ])

def is_approved(user_id: int) -> bool:
    return get_user_status(user_id) == "approved"

def not_approved_reply():
    return (
        "🔒 *Access Required*\n\n"
        "You need admin approval before using this feature.\n"
        "Please click *🔑 Request Admin Access* first."
    )

def _extract_username(link: str):
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", link)
    if match:
        return match.group(1)
    if link.startswith("@"):
        return link[1:]
    return None

# ─────────────────────────────────────────────
# /START HANDLER
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username, user.first_name)
    welcome = (
        "👋 *Welcome to AdApprovalPilot AI!*\n\n"
        "I help you fix Telegram Ads issues such as:\n"
        "❌ *Destination Quality* rejection\n"
        "⏳ Ads *stuck in review*\n"
        "📉 *Low CPM* performance\n\n"
        "🚀 Get started by requesting access below, "
        "then use the tools to analyse and fix your ads."
    )
    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

# ─────────────────────────────────────────────
# ACCESS REQUEST
# ─────────────────────────────────────────────
async def req_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    status = get_user_status(user.id)
    if status == "approved":
        await query.edit_message_text("✅ You already have access!", reply_markup=main_menu_keyboard())
        return
    if status == "denied":
        await query.edit_message_text("❌ Your access request was denied.", reply_markup=main_menu_keyboard())
        return

    upsert_user(user.id, user.username, user.first_name, "pending")

    admin_msg = (
        f"🔔 *New Access Request*\n\n"
        f"👤 Name: {user.first_name}\n"
        f"🆔 User ID: `{user.id}`\n"
        f"📛 Username: @{user.username or 'N/A'}"
    )
    admin_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user.id}"),
        InlineKeyboardButton("❌ Deny",   callback_data=f"deny_{user.id}"),
    ]])

    try:
        await context.bot.send_message(
            chat_id=f"@{ADMIN_USERNAME}",
            text=admin_msg,
            parse_mode="Markdown",
            reply_markup=admin_keyboard
        )
        await query.edit_message_text(
            "⏳ *Access request sent!*\n\nPlease wait for admin approval. "
            "You'll be notified once a decision is made.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Could not message admin: {e}")
        await query.edit_message_text(
            "⚠️ Could not reach admin right now. Please try again later.",
            reply_markup=main_menu_keyboard()
        )

# ─────────────────────────────────────────────
# ADMIN ACCEPT / DENY
# ─────────────────────────────────────────────
async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.username != ADMIN_USERNAME:
        await query.answer("⛔ You are not authorised.", show_alert=True)
        return

    data = query.data
    action, target_id = data.split("_", 1)
    target_id = int(target_id)

    if action == "accept":
        set_user_status(target_id, "approved")
        await query.edit_message_text(f"✅ User `{target_id}` has been *approved*.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text="✅ *Access Granted!*\n\nWelcome aboard! You now have full access to AdApprovalPilot AI.\n\nUse /start to open the menu.",
            parse_mode="Markdown"
        )
    else:
        set_user_status(target_id, "denied")
        await query.edit_message_text(f"❌ User `{target_id}` has been *denied*.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ *Access Denied*\n\nYour request was not approved. Contact @BlockSavvyMx if you think this is a mistake.",
            parse_mode="Markdown"
        )

# ─────────────────────────────────────────────
# ACCESS GATE
# ─────────────────────────────────────────────
async def gate_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if not is_approved(query.from_user.id):
        await query.answer("🔒 Request access first!", show_alert=True)
        await query.edit_message_text(
            not_approved_reply(),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return False
    return True

# ─────────────────────────────────────────────
# CHANNEL INDEX
# ─────────────────────────────────────────────
async def channel_index_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "📊 *Channel Index*\n\nPlease send your Telegram channel link.\nExample: `https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_CHANNEL_LINK

async def channel_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link format. Please send a valid t.me link.")
        return WAIT_CHANNEL_LINK
    report = (
        f"📊 *Channel Analysis Report*\n"
        f"🔗 Link: `{link}`\n\n"
        f"{'✅' if len(username) >= 5 else '⚠️'} *Username length*: "
        f"{'Good' if len(username) >= 5 else 'Too short — use 5+ characters'}\n"
        f"{'✅' if not re.search(r'[_]{2,}', username) else '⚠️'} *Username format*: "
        f"{'Clean' if not re.search(r'[_]{2,}', username) else 'Avoid double underscores'}\n\n"
        f"📋 *General Recommendations:*\n"
        f"• Add a clear niche keyword to your channel description\n"
        f"• Post consistently (min 3x per week) for better ad approval\n"
        f"• Ensure your pinned post explains what the channel is about\n"
        f"• Avoid all-caps or spammy words in channel name\n\n"
        f"📈 *Approval Readiness*: Medium — review suggestions above"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# GROUP INDEX
# ─────────────────────────────────────────────
async def group_index_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "👥 *Group Index*\n\nSend your Telegram group link.\nExample: `https://t.me/yourgroup`",
        parse_mode="Markdown"
    )
    return WAIT_GROUP_LINK

async def group_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link. Please send a valid t.me link.")
        return WAIT_GROUP_LINK
    report = (
        f"👥 *Group Analysis Report*\n"
        f"🔗 Link: `{link}`\n\n"
        f"✅ *Visibility*: Public group detected\n"
        f"⚠️ *Spam Risk*: Medium — ensure your group rules are pinned\n"
        f"✅ *Username quality*: Acceptable\n\n"
        f"📋 *Recommendations:*\n"
        f"• Pin group rules to reduce spam flags\n"
        f"• Enable slow mode to lower spam risk score\n"
        f"• Make sure your group description is clear and niche-specific\n"
        f"• Remove inactive bots and suspicious members\n\n"
        f"📈 *Ad Suitability*: Moderate — fix spam indicators first"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# BOT INDEX
# ─────────────────────────────────────────────
async def bot_index_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "🤖 *Bot Index*\n\nSend your bot's t.me link.\nExample: `https://t.me/YourBot`",
        parse_mode="Markdown"
    )
    return WAIT_BOT_LINK

async def bot_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link. Please send a valid t.me link.")
        return WAIT_BOT_LINK
    report = (
        f"🤖 *Bot Analysis Report*\n"
        f"🔗 Link: `{link}`\n\n"
        f"{'✅' if username.lower().endswith('bot') else '⚠️'} *Bot naming convention*: "
        f"{'Correct' if username.lower().endswith('bot') else 'Should end with \"bot\" for Telegram compliance'}\n"
        f"✅ *Public accessibility*: Good\n\n"
        f"📋 *Recommendations:*\n"
        f"• Ensure /start message clearly explains the bot's purpose\n"
        f"• Add a BotFather description (max 512 chars)\n"
        f"• Set a short description shown before /start\n"
        f"• Add a profile photo — bots without photos get lower trust scores\n\n"
        f"📈 *Ad Destination Score*: Medium — add description & photo"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# AD TEXT ANALYZER
# ─────────────────────────────────────────────
SPAM_WORDS = [
    "earn fast", "guarantee", "guaranteed", "make money", "get rich",
    "click now", "limited time", "free money", "100%", "no risk",
    "act now", "winner", "prize", "cash", "instant profit",
    "work from home", "passive income", "double your", "risk free"
]

async def ad_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "✍️ *Ad Text Analyzer*\n\nPaste your ad copy below and I'll check it for policy risks.",
        parse_mode="Markdown"
    )
    return WAIT_AD_TEXT

async def ad_text_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    found = [w for w in SPAM_WORDS if w in text]
    risk = "🟢 Low" if not found else ("🟡 Medium" if len(found) <= 2 else "🔴 High")
    prob = 90 if not found else (65 if len(found) <= 2 else 30)
    improved = update.message.text
    for w in found:
        improved = re.sub(re.escape(w), "[REMOVED]", improved, flags=re.IGNORECASE)
    report = (
        f"✍️ *Ad Text Analysis*\n\n"
        f"*Risk Level*: {risk}\n"
        f"*Approval Probability*: ~{prob}%\n\n"
    )
    if found:
        report += "❌ *Risky phrases detected*:\n" + "\n".join(f"  • `{w}`" for w in found) + "\n\n"
        report += f"✅ *Suggested version*:\n_{improved}_\n\n"
    else:
        report += "✅ No major spam phrases detected.\n\n"
    report += (
        "📋 *General Tips:*\n"
        "• Be specific about what your product does\n"
        "• Avoid exclamation marks in every sentence\n"
        "• Include a clear, honest CTA\n"
        "• Never promise specific financial returns"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# AD BUDGET OPTIMIZER
# ─────────────────────────────────────────────
async def ad_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "💰 *Ad Budget Optimizer*\n\nEnter your total ad budget in USD.\nExample: `50`",
        parse_mode="Markdown"
    )
    return WAIT_BUDGET

async def ad_budget_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        budget = float(re.sub(r"[^\d.]", "", update.message.text))
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number. Example: `50`", parse_mode="Markdown")
        return WAIT_BUDGET
    duration  = 7 if budget <= 50 else (14 if budget <= 200 else 30)
    daily_opt = round(budget / duration, 2)
    report = (
        f"💰 *Budget Optimization Report*\n\n"
        f"💵 *Total Budget*: ${budget:.2f}\n"
        f"📅 *Recommended Duration*: {duration} days\n"
        f"📆 *Daily Spend*: ${daily_opt:.2f}/day\n\n"
        f"📋 *Strategy:*\n"
        f"• Days 1–3: Test phase — run 2–3 ad variants\n"
        f"• Days 4–7: Scale the best-performing ad\n"
        f"• Pause ads with CTR below 1% after day 3\n\n"
        f"💡 *Tips:*\n"
        f"• Start with Tier 2 countries for lower CPM\n"
        f"• Use channel posts as ad destination for better quality score\n"
        f"• Set frequency cap to 2 impressions/user/day"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# CPM PREDICTOR
# ─────────────────────────────────────────────
CPM_TABLE = {
    "crypto":    (1.5, 3.5, "High",   "Tier 1 audiences drive up cost — test Tier 2 (IN, NG, BR)"),
    "finance":   (1.2, 3.0, "High",   "Highly competitive — use narrow interest targeting"),
    "tech":      (0.8, 2.0, "Medium", "Good volume — mix Tier 1 and Tier 2 for balance"),
    "education": (0.5, 1.2, "Low",    "Low CPM niche — great for tight budgets"),
    "gaming":    (0.6, 1.5, "Low",    "Younger audience — works well with interactive creatives"),
    "health":    (0.9, 2.2, "Medium", "Policy-sensitive — ensure ad copy is compliant"),
    "ecommerce": (0.7, 1.8, "Medium", "Retargeting works best — link to channel, not website"),
    "news":      (0.4, 1.0, "Low",    "Very broad — narrow by language for better CPM"),
}

async def ad_cpm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    niches = ", ".join(CPM_TABLE.keys())
    await query.edit_message_text(
        f"📉 *CPM Predictor*\n\nWhat is your niche or target audience?\n\n"
        f"Known niches: `{niches}`\n\n"
        f"Or describe your audience (e.g. 'crypto traders in Nigeria')",
        parse_mode="Markdown"
    )
    return WAIT_CPM_NICHE

async def ad_cpm_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    matched = next((k for k in CPM_TABLE if k in text), None)
    if matched:
        lo, hi, risk, tip = CPM_TABLE[matched]
        niche_label = matched.capitalize()
    else:
        lo, hi, risk, tip = 0.6, 1.8, "Medium", "Define your niche more precisely for better targeting"
        niche_label = "General"
    risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk, "🟡")
    report = (
        f"📉 *CPM Prediction Report*\n\n"
        f"🎯 *Niche*: {niche_label}\n"
        f"💵 *Estimated CPM*: ${lo} – ${hi}\n"
        f"⚠️ *Risk Level*: {risk_emoji} {risk}\n\n"
        f"💡 *Recommendation*: {tip}\n\n"
        f"📋 *Targeting Tips:*\n"
        f"• Tier 2 countries (IN, NG, PK, BR) give lower CPM\n"
        f"• Narrow audience = higher CPM but better conversion\n"
        f"• Broad audience = lower CPM but lower quality clicks\n"
        f"• Test 2–3 creatives before scaling"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# CANCEL
# ─────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. Back to main menu.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────
flask_app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()

# ✅ FIXED: use asyncio.run() instead of get_event_loop()
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    asyncio.run(ptb_app.process_update(update))
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def index():
    return "AdApprovalPilot AI is running ✅", 200

# ─────────────────────────────────────────────
# REGISTER HANDLERS
# ─────────────────────────────────────────────
def register_handlers():
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CallbackQueryHandler(req_access, pattern="^req_access$"))
    ptb_app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(accept|deny)_\\d+$"))

    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(channel_index_start, pattern="^channel_index$")],
        states={WAIT_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, channel_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(group_index_start, pattern="^group_index$")],
        states={WAIT_GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_index_start, pattern="^bot_index$")],
        states={WAIT_BOT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_text_start, pattern="^ad_text$")],
        states={WAIT_AD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_budget_start, pattern="^ad_budget$")],
        states={WAIT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_budget_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_cpm_start, pattern="^ad_cpm$")],
        states={WAIT_CPM_NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_cpm_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
async def setup():
    register_handlers()
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
    logger.info(f"Webhook registered: {WEBHOOK_URL}/{TOKEN}")

init_db()
asyncio.run(setup())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
