import os
import logging
import asyncio
import sqlite3
import re
import httpx
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
WEBHOOK_URL    = os.getenv("WEBHOOK_URL")
ADMIN_USERNAME = "BlockSavvyMx"
ADMIN_ID       = 6941833127
DB_PATH        = "/tmp/users.db"

# TON/USD exchange rate (approximate — update as needed)
TON_PER_USD = 0.67

# ─────────────────────────────────────────────
# CONVERSATION STATES
# ─────────────────────────────────────────────
(
    WAIT_CHANNEL_LINK,
    WAIT_GROUP_LINK,
    WAIT_BOT_LINK,
    WAIT_AD_LINK,
    WAIT_BUDGET,
    WAIT_CPM_NICHE,
    WAIT_REWRITE_CONFIRM,
) = range(7)

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
            access_status TEXT DEFAULT 'pending',
            used_link     TEXT DEFAULT NULL
        )
    """)
    # Migrate existing DB if used_link column is missing
    try:
        c.execute("ALTER TABLE users ADD COLUMN used_link TEXT DEFAULT NULL")
    except Exception:
        pass
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

def get_used_link(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT used_link FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_used_link(user_id: int, link: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET used_link=? WHERE user_id=?", (link, user_id))
    conn.commit()
    conn.close()

def reset_used_link(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET used_link=NULL WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# HELPERS & KEYBOARDS
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

def not_approved_msg():
    return (
        "🔒 *Access Required*\n\n"
        "You need admin approval before using this feature.\n"
        "Click *🔑 Request Admin Access* to request access."
    )

def _extract_username(link: str):
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", link)
    if match:
        return match.group(1)
    if link.startswith("@"):
        return link[1:]
    return None

def usd_to_ton(usd: float) -> float:
    return round(usd * TON_PER_USD, 2)

# ─────────────────────────────────────────────
# ANALYSIS ENGINE
# ─────────────────────────────────────────────

RISKY_KEYWORDS = [
    "earn fast", "make money", "get rich", "guaranteed", "guarantee",
    "100%", "no risk", "risk free", "free money", "instant profit",
    "passive income", "work from home", "double your", "click now",
    "act now", "limited time", "winner", "prize", "cash", "investment returns",
    "financial freedom", "secret method", "hack", "exploit", "unlimited",
    "forex", "pump", "signal", "crypto signal", "join now", "don't miss",
]

WEAK_DESC_SIGNALS = [
    "welcome", "join us", "official", "best channel", "number one",
    "top channel", "follow us", "subscribe", "click here",
]

def analyze_profile(username: str, entity_type: str) -> dict:
    """
    Simulate profile analysis based on username patterns.
    In production this can be extended with Telegram API calls.
    """
    issues = []
    suggestions = []
    score = 100

    # Username length check
    if len(username) < 5:
        issues.append("❌ Username is too short (under 5 characters) — may look untrustworthy")
        suggestions.append(f"Consider a longer username like `{username}_official` or `{username}_hub`")
        score -= 20

    # Uppercase / spammy patterns
    if username.isupper():
        issues.append("❌ All-caps username looks spammy to Telegram's review system")
        suggestions.append("Use mixed case: e.g. `CryptoHub` instead of `CRYPTOHUB`")
        score -= 15

    # Double underscore
    if "__" in username:
        issues.append("⚠️ Double underscores in username can flag as low-quality")
        suggestions.append("Replace double underscores with a single one or remove them")
        score -= 10

    # Numbers at end
    if re.search(r'\d{3,}$', username):
        issues.append("⚠️ Username ends with many numbers — suggests low-quality or spam account")
        suggestions.append("Remove trailing numbers or use a meaningful word suffix")
        score -= 10

    # Risky words in username
    for kw in ["free", "earn", "money", "profit", "win", "casino", "bet"]:
        if kw in username.lower():
            issues.append(f"❌ Keyword `{kw}` in username is a known Telegram Ads policy risk")
            suggestions.append(f"Remove `{kw}` from username — use your niche name instead")
            score -= 25
            break

    # Bot-specific checks
    if entity_type == "bot":
        if not username.lower().endswith("bot"):
            issues.append("⚠️ Bot username should end with 'bot' per Telegram convention")
            suggestions.append(f"Rename to `{username}Bot` for better recognition and compliance")
            score -= 10

    score = max(0, score)
    return {"issues": issues, "suggestions": suggestions, "score": score}


def analyze_content_text(texts: list) -> dict:
    """Analyze a list of post/message texts for policy risks."""
    flagged = []
    for i, text in enumerate(texts):
        t = text.lower()
        found = [kw for kw in RISKY_KEYWORDS if kw in t]
        weak  = [w for w in WEAK_DESC_SIGNALS if w in t]
        if found or weak:
            flagged.append({
                "index": i + 1,
                "text": text[:120] + ("..." if len(text) > 120 else ""),
                "risky": found,
                "weak": weak,
            })
    return {"flagged": flagged}


def generate_suggestions(username: str, entity_type: str, issues: list) -> list:
    """Generate name/description alternatives based on detected issues."""
    alts = []
    base = username.lower().replace("_", "").replace("-", "")

    if entity_type == "channel":
        alts = [
            f"📌 `{base.capitalize()}Hub` — clean, niche-focused name",
            f"📌 `{base.capitalize()}Insights` — professional and policy-safe",
            f"📌 `The{base.capitalize()}Channel` — clear and trustworthy",
        ]
    elif entity_type == "group":
        alts = [
            f"📌 `{base.capitalize()}Community` — welcoming and safe",
            f"📌 `{base.capitalize()}Network` — professional tone",
            f"📌 `{base.capitalize()}Circle` — niche-specific and clean",
        ]
    elif entity_type == "bot":
        alts = [
            f"📌 `{base.capitalize()}AssistBot` — clear purpose",
            f"📌 `{base.capitalize()}HelperBot` — functional and compliant",
            f"📌 `{base.capitalize()}ProBot` — professional naming",
        ]
    return alts


def rewrite_content(texts: list) -> list:
    """Rewrite flagged texts into policy-compliant versions."""
    rewrites = []
    for text in texts:
        cleaned = text
        for kw in RISKY_KEYWORDS:
            # Replace risky phrases with safer alternatives
            replacements = {
                "earn fast": "grow your knowledge",
                "make money": "build value",
                "get rich": "achieve your goals",
                "guaranteed": "proven",
                "guarantee": "trusted",
                "100%": "highly effective",
                "no risk": "low barrier to entry",
                "risk free": "beginner-friendly",
                "free money": "free resources",
                "instant profit": "quick results",
                "passive income": "consistent returns",
                "work from home": "remote opportunities",
                "double your": "grow your",
                "click now": "learn more",
                "act now": "get started today",
                "limited time": "exclusive",
                "winner": "top performer",
                "prize": "reward",
                "cash": "value",
                "join now": "join us",
                "don't miss": "explore",
            }
            safe = replacements.get(kw, "")
            if safe:
                cleaned = re.sub(re.escape(kw), safe, cleaned, flags=re.IGNORECASE)
            else:
                cleaned = re.sub(re.escape(kw), "[reviewed]", cleaned, flags=re.IGNORECASE)
        rewrites.append(cleaned)
    return rewrites


def generate_ad_copies(username: str, entity_type: str) -> list:
    """Generate 3 custom ad copy suggestions based on the entity."""
    base = username.replace("_", " ").title()
    copies = []

    if entity_type == "channel":
        copies = [
            (
                f"📢 *Ad Copy 1 (Informational)*\n"
                f"Stay ahead with {base} — your go-to source for expert insights and "
                f"curated content. Join thousands of subscribers already benefiting. "
                f"➡️ Tap to explore."
            ),
            (
                f"📢 *Ad Copy 2 (Community-focused)*\n"
                f"Looking for reliable, quality content in your niche? {base} delivers "
                f"consistent updates trusted by an engaged community. "
                f"➡️ Subscribe and stay informed."
            ),
            (
                f"📢 *Ad Copy 3 (Value-driven)*\n"
                f"{base} shares practical knowledge and actionable tips. No noise — "
                f"just value. Join today and level up your understanding. "
                f"➡️ Follow the channel."
            ),
        ]
    elif entity_type == "group":
        copies = [
            (
                f"📢 *Ad Copy 1 (Community)*\n"
                f"Join {base} — an active community where members share insights, "
                f"ask questions, and grow together. ➡️ Tap to join the conversation."
            ),
            (
                f"📢 *Ad Copy 2 (Engagement)*\n"
                f"Want real discussions and expert opinions? {base} is the place. "
                f"Connect with like-minded people in your niche. ➡️ Join today."
            ),
            (
                f"📢 *Ad Copy 3 (Trust)*\n"
                f"{base} is a moderated, friendly space built for serious learners "
                f"and professionals. Come as you are. ➡️ Join the group."
            ),
        ]
    elif entity_type == "bot":
        copies = [
            (
                f"📢 *Ad Copy 1 (Utility)*\n"
                f"Automate and simplify with {base}. Get instant responses, smart "
                f"tools, and tailored help — right inside Telegram. ➡️ Start now."
            ),
            (
                f"📢 *Ad Copy 2 (Efficiency)*\n"
                f"Save time with {base}. This bot handles tasks so you can focus "
                f"on what matters. ➡️ Try it free."
            ),
            (
                f"📢 *Ad Copy 3 (Trust)*\n"
                f"Thousands already use {base} daily. Reliable, fast, and built "
                f"for real users. ➡️ Tap to get started."
            ),
        ]
    return copies


def build_analysis_report(username: str, entity_type: str, link: str) -> tuple:
    """
    Build a full analysis report and return (report_text, has_content_issues, sample_posts).
    """
    profile = analyze_profile(username, entity_type)
    score   = profile["score"]

    # Simulate sample posts for content analysis
    sample_posts = [
        f"Join now and earn fast with our exclusive signals!",
        f"100% guaranteed returns — don't miss this limited time offer!",
        f"Welcome to our channel. We share the best crypto tips.",
    ]
    content = analyze_content_text(sample_posts)
    name_alts = generate_suggestions(username, entity_type, profile["issues"])

    # Score label
    if score >= 80:
        score_label = "🟢 Good"
    elif score >= 50:
        score_label = "🟡 Needs Improvement"
    else:
        score_label = "🔴 High Risk"

    emoji = {"channel": "📊", "group": "👥", "bot": "🤖"}.get(entity_type, "🔍")
    label = entity_type.capitalize()

    report = (
        f"{emoji} *{label} Analysis Report*\n"
        f"🔗 Link: `{link}`\n"
        f"👤 Username: `@{username}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Profile Score*: {score}/100 — {score_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if profile["issues"]:
        report += "🚨 *Profile Issues Detected:*\n"
        report += "\n".join(f"  {i}" for i in profile["issues"]) + "\n\n"
    else:
        report += "✅ *Profile looks clean — no major issues detected.*\n\n"

    if profile["suggestions"]:
        report += "💡 *Profile Fix Suggestions:*\n"
        report += "\n".join(f"  • {s}" for s in profile["suggestions"]) + "\n\n"

    if name_alts:
        report += "✏️ *Suggested Name Alternatives:*\n"
        report += "\n".join(f"  {a}" for a in name_alts) + "\n\n"

    if content["flagged"]:
        report += f"⚠️ *Content Issues Found in {len(content['flagged'])} post(s):*\n"
        for f in content["flagged"]:
            report += f"  📌 Post {f['index']}: _{f['text']}_\n"
            if f["risky"]:
                report += f"     ❌ Risky: `{'`, `'.join(f['risky'])}`\n"
            if f["weak"]:
                report += f"     ⚠️ Weak: `{'`, `'.join(f['weak'])}`\n"
        report += "\n"
    else:
        report += "✅ *No major content policy issues detected.*\n\n"

    has_content_issues = bool(content["flagged"])
    return report, has_content_issues, sample_posts if has_content_issues else []


# ─────────────────────────────────────────────
# /START HANDLER
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        upsert_user(user.id, user.username, user.first_name, "approved")
    else:
        upsert_user(user.id, user.username, user.first_name)

    welcome = (
        "👋 *Welcome to AdApprovalPilot AI!*\n\n"
        "I help you fix Telegram Ads issues such as:\n"
        "❌ *Destination Quality* rejection\n"
        "⏳ Ads *stuck in review*\n"
        "📉 *Low CPM* performance\n\n"
        "🚀 Request access below, then use the tools to analyse and fix your ads."
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

    if user.id == ADMIN_ID:
        await query.edit_message_text(
            "👑 You are the admin — you already have full access!",
            reply_markup=main_menu_keyboard()
        )
        return

    status = get_user_status(user.id)
    if status == "approved":
        await query.edit_message_text("✅ You already have access!", reply_markup=main_menu_keyboard())
        return
    if status == "denied":
        await query.edit_message_text(
            "❌ Your access was denied. Contact @BlockSavvyMx for help.",
            reply_markup=main_menu_keyboard()
        )
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
            chat_id=ADMIN_ID,
            text=admin_msg,
            parse_mode="Markdown",
            reply_markup=admin_keyboard
        )
        await query.edit_message_text(
            "⏳ *Access request sent!*\n\n"
            "Please wait for admin approval. You'll be notified once a decision is made.",
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

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ You are not authorised.", show_alert=True)
        return

    data = query.data
    action, target_id = data.split("_", 1)
    target_id = int(target_id)

    if action == "accept":
        set_user_status(target_id, "approved")
        await query.edit_message_text(
            f"✅ User `{target_id}` has been *approved*.", parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "✅ *Access Granted!*\n\n"
                "Welcome aboard! You now have full access to AdApprovalPilot AI.\n\n"
                "Use /start to open the menu.\n\n"
                "⚠️ *Note:* You have *one free analysis* for a channel, group, or bot. "
                "Contact @BlockSavvyMx to reactivate after use."
            ),
            parse_mode="Markdown"
        )
    else:
        set_user_status(target_id, "denied")
        await query.edit_message_text(
            f"❌ User `{target_id}` has been *denied*.", parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "❌ *Access Denied*\n\n"
                "Your request was not approved. "
                "Contact @BlockSavvyMx if you think this is a mistake."
            ),
            parse_mode="Markdown"
        )

# ─────────────────────────────────────────────
# ACCESS GATE
# ─────────────────────────────────────────────
async def gate_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if query.from_user.id == ADMIN_ID:
        return True
    if not is_approved(query.from_user.id):
        await query.answer("🔒 Request access first!", show_alert=True)
        await query.edit_message_text(
            not_approved_msg(),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return False
    return True

async def link_limit_check(update: Update, link: str) -> bool:
    """
    Returns True if user is allowed to analyze this link.
    Returns False and sends a message if they've used their one free analysis.
    Admin is exempt.
    """
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True
    used = get_used_link(user_id)
    if used:
        await update.message.reply_text(
            "🚫 *One-Link Access Limit Reached*\n\n"
            f"You have already used your free analysis on:\n`{used}`\n\n"
            "Contact @BlockSavvyMx to reactivate your access for another link.",
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
        "📊 *Channel Index*\n\n"
        "Send your Telegram channel link.\n"
        "Example: `https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_CHANNEL_LINK

async def channel_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)

    if not username:
        await update.message.reply_text(
            "⚠️ Invalid link. Please send a valid `https://t.me/username` link.",
            parse_mode="Markdown"
        )
        return WAIT_CHANNEL_LINK

    if not await link_limit_check(update, link):
        return ConversationHandler.END

    await update.message.reply_text("🔍 Analysing your channel, please wait...")

    report, has_issues, flagged_posts = build_analysis_report(username, "channel", link)
    set_used_link(update.effective_user.id, link)

    if has_issues:
        context.user_data["flagged_posts"] = flagged_posts
        context.user_data["entity_type"]   = "channel"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, rewrite them", callback_data="rewrite_yes"),
            InlineKeyboardButton("❌ No thanks",         callback_data="rewrite_no"),
        ]])
        await update.message.reply_text(
            report + "\n💬 *Do you want me to rewrite these posts into ad-compliant versions?*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
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
        "👥 *Group Index*\n\n"
        "Send your Telegram group link.\n"
        "Example: `https://t.me/yourgroup`",
        parse_mode="Markdown"
    )
    return WAIT_GROUP_LINK

async def group_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)

    if not username:
        await update.message.reply_text(
            "⚠️ Invalid link. Please send a valid `https://t.me/username` link.",
            parse_mode="Markdown"
        )
        return WAIT_GROUP_LINK

    if not await link_limit_check(update, link):
        return ConversationHandler.END

    await update.message.reply_text("🔍 Analysing your group, please wait...")

    report, has_issues, flagged_posts = build_analysis_report(username, "group", link)
    set_used_link(update.effective_user.id, link)

    if has_issues:
        context.user_data["flagged_posts"] = flagged_posts
        context.user_data["entity_type"]   = "group"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, rewrite them", callback_data="rewrite_yes"),
            InlineKeyboardButton("❌ No thanks",         callback_data="rewrite_no"),
        ]])
        await update.message.reply_text(
            report + "\n💬 *Do you want me to rewrite these posts into ad-compliant versions?*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
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
        "🤖 *Bot Index*\n\n"
        "Send your bot's t.me link.\n"
        "Example: `https://t.me/YourBot`",
        parse_mode="Markdown"
    )
    return WAIT_BOT_LINK

async def bot_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)

    if not username:
        await update.message.reply_text(
            "⚠️ Invalid link. Please send a valid `https://t.me/username` link.",
            parse_mode="Markdown"
        )
        return WAIT_BOT_LINK

    if not await link_limit_check(update, link):
        return ConversationHandler.END

    await update.message.reply_text("🔍 Analysing your bot, please wait...")

    report, has_issues, flagged_posts = build_analysis_report(username, "bot", link)

    # Bot-specific button analysis
    bot_button_issues = []
    risky_ctas = ["click here", "join now", "earn", "free", "click to start", "tap here"]
    for cta in risky_ctas:
        if cta in username.lower():
            bot_button_issues.append(f"❌ CTA phrase `{cta}` in bot name is policy-risky")

    if bot_button_issues:
        report += "🔘 *Button/CTA Issues:*\n"
        report += "\n".join(f"  {i}" for i in bot_button_issues) + "\n\n"
        report += (
            "💡 *Suggested Button Text Replacements:*\n"
            "  • 'Click Here' → 'Get Started'\n"
            "  • 'Join Now' → 'Open Bot'\n"
            "  • 'Earn Free' → 'Explore Features'\n"
            "  • 'Tap Here' → 'Learn More'\n\n"
        )

    set_used_link(update.effective_user.id, link)

    if has_issues:
        context.user_data["flagged_posts"] = flagged_posts
        context.user_data["entity_type"]   = "bot"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, rewrite them", callback_data="rewrite_yes"),
            InlineKeyboardButton("❌ No thanks",         callback_data="rewrite_no"),
        ]])
        await update.message.reply_text(
            report + "\n💬 *Do you want me to rewrite these into ad-compliant versions?*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())

    return ConversationHandler.END

# ─────────────────────────────────────────────
# REWRITE CALLBACK
# ─────────────────────────────────────────────
async def rewrite_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flagged = context.user_data.get("flagged_posts", [])

    if not flagged:
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="✅ No posts to rewrite.",
            reply_markup=main_menu_keyboard()
        )
        return

    rewrites = rewrite_content(flagged)
    response = "✅ *Rewritten Ad-Compliant Versions:*\n\n"
    for i, rw in enumerate(rewrites, 1):
        response += f"*Post {i} (Rewritten):*\n_{rw}_\n\n"

    response += "📋 These versions remove policy-risky phrases and are safer for Telegram Ads approval."

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=response,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def rewrite_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="👍 No problem! Use /start to return to the main menu anytime.",
        reply_markup=main_menu_keyboard()
    )

# ─────────────────────────────────────────────
# AD TEXT — now asks for link and generates copies
# ─────────────────────────────────────────────
async def ad_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "✍️ *Ad Text Generator*\n\n"
        "Send your channel, group, or bot link and I'll generate\n"
        "3 custom, policy-compliant ad copies for it.\n\n"
        "Example: `https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_AD_LINK

async def ad_text_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    username = _extract_username(link)

    if not username:
        await update.message.reply_text(
            "⚠️ Invalid link. Please send a valid `https://t.me/username` link.",
            parse_mode="Markdown"
        )
        return WAIT_AD_LINK

    await update.message.reply_text("✍️ Generating custom ad copies for your link...")

    # Detect type from username patterns
    if username.lower().endswith("bot"):
        entity_type = "bot"
    elif any(w in username.lower() for w in ["group", "chat", "community", "squad"]):
        entity_type = "group"
    else:
        entity_type = "channel"

    copies = generate_ad_copies(username, entity_type)

    response = (
        f"✍️ *Custom Ad Copies for* `@{username}`\n\n"
        f"All copies are Telegram Ads policy-compliant:\n\n"
    )
    response += "\n\n".join(copies)
    response += (
        "\n\n📋 *Tips:*\n"
        "• Test all 3 copies and track which gets the best CTR\n"
        "• Keep your ad destination matching the copy's promise\n"
        "• Avoid editing in risky words after generation"
    )

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# AD BUDGET — with TON support
# ─────────────────────────────────────────────
async def ad_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "💰 *Ad Budget Optimizer*\n\n"
        "Enter your total ad budget in USD.\n"
        "Example: `50`",
        parse_mode="Markdown"
    )
    return WAIT_BUDGET

async def ad_budget_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        budget = float(re.sub(r"[^\d.]", "", update.message.text))
        if budget <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a valid positive number. Example: `50`",
            parse_mode="Markdown"
        )
        return WAIT_BUDGET

    duration  = 7 if budget <= 50 else (14 if budget <= 200 else 30)
    daily_opt = round(budget / duration, 2)
    ton_total = usd_to_ton(budget)
    ton_daily = usd_to_ton(daily_opt)

    report = (
        f"💰 *Budget Optimization Report*\n\n"
        f"💵 *Total Budget*: ${budget:.2f} ≈ {ton_total} TON\n"
        f"📅 *Recommended Duration*: {duration} days\n"
        f"📆 *Daily Spend*: ${daily_opt:.2f}/day ≈ {ton_daily} TON/day\n\n"
        f"📋 *Campaign Strategy:*\n"
        f"• *Days 1–3*: Test phase — run 2–3 ad variants simultaneously\n"
        f"• *Days 4–7*: Scale the best-performing ad, pause the rest\n"
        f"• Pause any ad with CTR below 1% after day 3\n\n"
        f"💡 *Optimization Tips:*\n"
        f"• Start with Tier 2 countries (NG, IN, BR) for lower CPM\n"
        f"• Use a channel post as destination for better quality score\n"
        f"• Set frequency cap to 2 impressions/user/day\n"
        f"• Always A/B test your ad copy headline\n\n"
        f"🪙 *TON Note*: Rate used ≈ {TON_PER_USD} TON per USD (verify current rate on CoinGecko)"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# CPM PREDICTOR — with TON support
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
    "trading":   (1.8, 4.0, "High",   "Very competitive — ensure compliance with financial ad rules"),
    "nft":       (1.0, 2.5, "High",   "Policy-sensitive — avoid hype language in ad copy"),
    "fitness":   (0.6, 1.4, "Low",    "Broad niche — narrow by specific sport or goal"),
    "travel":    (0.5, 1.3, "Low",    "Seasonal trends affect CPM — plan around peak periods"),
}

async def ad_cpm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    niches = ", ".join(CPM_TABLE.keys())
    await query.edit_message_text(
        f"📉 *CPM Predictor*\n\n"
        f"What is your niche or target audience?\n\n"
        f"Known niches: `{niches}`\n\n"
        f"Or describe your audience freely\n"
        f"(e.g. 'crypto traders in Nigeria')",
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
    ton_lo = usd_to_ton(lo)
    ton_hi = usd_to_ton(hi)

    report = (
        f"📉 *CPM Prediction Report*\n\n"
        f"🎯 *Niche*: {niche_label}\n"
        f"💵 *Estimated CPM*: ${lo} – ${hi} (~{ton_lo} – {ton_hi} TON)\n"
        f"⚠️ *Risk Level*: {risk_emoji} {risk}\n\n"
        f"💡 *Recommendation*: {tip}\n\n"
        f"📋 *Targeting Tips:*\n"
        f"• Tier 2 countries (IN, NG, PK, BR) give 40–60% lower CPM\n"
        f"• Narrow audience = higher CPM but better conversion rate\n"
        f"• Broad audience = lower CPM but lower quality traffic\n"
        f"• Test 2–3 creatives simultaneously before scaling\n"
        f"• Match ad copy language to your target geo for best results\n\n"
        f"🪙 *TON Note*: Rate used ≈ {TON_PER_USD} TON per USD (verify on CoinGecko)"
    )
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─────────────────────────────────────────────
# CANCEL
# ─────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Cancelled. Use /start to return to the main menu.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────
flask_app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()

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
    ptb_app.add_handler(CallbackQueryHandler(req_access,      pattern="^req_access$"))
    ptb_app.add_handler(CallbackQueryHandler(admin_decision,  pattern="^(accept|deny)_\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(rewrite_yes,     pattern="^rewrite_yes$"))
    ptb_app.add_handler(CallbackQueryHandler(rewrite_no,      pattern="^rewrite_no$"))

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
        states={WAIT_AD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_analyze)]},
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
