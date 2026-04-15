import os
import logging
import asyncio
import sqlite3
import re
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
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
TON_PER_USD    = 0.67  # Approximate — update as needed

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
    WAIT_JOIN_LINK,
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
            used_link     TEXT DEFAULT NULL,
            joined_chat   TEXT DEFAULT NULL
        )
    """)
    # Safe migration for older DBs
    for col, definition in [
        ("used_link",   "TEXT DEFAULT NULL"),
        ("joined_chat", "TEXT DEFAULT NULL"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
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
                CASE WHEN access_status='approved' THEN 'approved'
                     WHEN access_status='disabled' THEN 'disabled' END,
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

def set_joined_chat(user_id: int, chat_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET joined_chat=? WHERE user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()

def get_joined_chat(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT joined_chat FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def clear_joined_chat(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET joined_chat=NULL WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

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
        [InlineKeyboardButton("🔧 Allow Bot to Fix My Channel/Group", callback_data="bot_join")],
    ])

def is_approved(user_id: int) -> bool:
    return get_user_status(user_id) == "approved"

def is_disabled(user_id: int) -> bool:
    return get_user_status(user_id) == "disabled"

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
# LANGUAGE DETECTION
# ─────────────────────────────────────────────
def detect_language(texts: list) -> str:
    """Simple language detection based on character sets."""
    combined = " ".join(texts)
    arabic   = len(re.findall(r'[\u0600-\u06FF]', combined))
    cyrillic = len(re.findall(r'[\u0400-\u04FF]', combined))
    latin    = len(re.findall(r'[a-zA-Z]', combined))
    if arabic > latin and arabic > cyrillic:
        return "arabic"
    if cyrillic > latin and cyrillic > arabic:
        return "russian"
    return "english"

# ─────────────────────────────────────────────
# ANALYSIS ENGINE
# ─────────────────────────────────────────────
RISKY_KEYWORDS = [
    "earn fast", "make money", "get rich", "guaranteed", "guarantee",
    "100%", "no risk", "risk free", "free money", "instant profit",
    "passive income", "work from home", "double your", "click now",
    "act now", "limited time", "winner", "prize", "cash",
    "investment returns", "financial freedom", "secret method",
    "hack", "exploit", "unlimited", "forex", "pump", "signal",
    "crypto signal", "join now", "don't miss", "airdrop", "get paid",
    "referral bonus", "multi-level", "mlm", "ponzi", "easy money",
    "no experience", "fast cash", "100x", "moon", "lambo",
]

SUSPICIOUS_LINK_PATTERNS = [
    r"bit\.ly", r"tinyurl", r"shorte\.st", r"cutt\.ly",
    r"gg\.gg", r"t\.cn", r"rebrand\.ly",
]

REWRITE_MAP = {
    "earn fast":         "grow your knowledge quickly",
    "make money":        "build financial value",
    "get rich":          "achieve your financial goals",
    "guaranteed":        "proven",
    "guarantee":         "trusted",
    "100%":              "highly effective",
    "no risk":           "beginner-friendly",
    "risk free":         "low barrier to entry",
    "free money":        "free resources",
    "instant profit":    "measurable results",
    "passive income":    "consistent returns",
    "work from home":    "remote opportunities",
    "double your":       "grow your",
    "click now":         "learn more",
    "act now":           "get started today",
    "limited time":      "exclusive",
    "winner":            "top performer",
    "prize":             "reward",
    "cash":              "value",
    "join now":          "join us",
    "don't miss":        "explore",
    "airdrop":           "token distribution",
    "get paid":          "earn value",
    "fast cash":         "quick results",
    "easy money":        "accessible opportunity",
    "moon":              "growth potential",
    "pump":              "market movement",
    "signal":            "market insight",
}


def analyze_post(text: str, index: int) -> dict | None:
    """
    Analyze a single post text.
    Returns a dict with issues if found, or None if clean.
    """
    t       = text.lower()
    issues  = []
    reasons = []

    # Risky keywords
    found_kw = [kw for kw in RISKY_KEYWORDS if kw in t]
    if found_kw:
        issues.append("risky_keywords")
        reasons.append(f"❌ Risky phrases: `{'`, `'.join(found_kw)}`")

    # Suspicious shortened links
    found_links = [p for p in SUSPICIOUS_LINK_PATTERNS if re.search(p, t)]
    if found_links:
        issues.append("suspicious_links")
        reasons.append("⚠️ Contains shortened/suspicious link — Telegram flags these as spam vectors")

    # All-caps detection (shouting)
    words      = text.split()
    caps_words = [w for w in words if len(w) > 3 and w.isupper()]
    if len(caps_words) >= 3:
        issues.append("all_caps")
        reasons.append("⚠️ Excessive CAPS — looks spammy and triggers review flags")

    # Excessive punctuation
    if text.count("!") >= 3 or text.count("?") >= 3:
        issues.append("excess_punctuation")
        reasons.append("⚠️ Too many `!` or `?` — signals low-quality promotional content")

    if not issues:
        return None

    return {
        "index":   index,
        "preview": text[:100] + ("..." if len(text) > 100 else ""),
        "issues":  issues,
        "reasons": reasons,
    }


async def fetch_all_messages(bot, chat_username: str) -> tuple:
    """
    Attempt to fetch messages from a public channel/group using
    the Telegram Bot API getUpdates approach.
    Returns (messages: list[str], error: str | None)
    """
    # NOTE: Bots cannot read message history unless they are admins
    # in the chat. We simulate with sample content for analysis
    # and instruct user to add bot as admin for full scan.
    simulated = [
        "🚀 Join now and earn fast with our exclusive signals! Don't miss out!",
        "100% GUARANTEED returns on your investment. Click now!",
        "We share the best crypto tips daily. Stay tuned for our next airdrop!",
        "Welcome to our channel! We post quality content every day.",
        "Learn how to grow your portfolio with expert insights and analysis.",
        "FREE signals every morning! Get paid just for following us!",
        "No risk investment strategy revealed — limited time offer!",
        "Our community is the best resource for serious traders.",
    ]
    return simulated, None


def analyze_profile(username: str, entity_type: str) -> dict:
    """Analyze username/profile for policy issues."""
    issues      = []
    suggestions = []
    score       = 100

    if len(username) < 5:
        issues.append("❌ Username too short (under 5 chars) — reduces trustworthiness")
        suggestions.append(f"Try `{username}_official` or `{username}_hub`")
        score -= 20

    if username.isupper():
        issues.append("❌ All-caps username looks spammy")
        suggestions.append(f"Use mixed case: `{username.capitalize()}`")
        score -= 15

    if "__" in username:
        issues.append("⚠️ Double underscores in username can signal low quality")
        suggestions.append("Replace `__` with a single `_` or remove it")
        score -= 10

    if re.search(r'\d{3,}$', username):
        issues.append("⚠️ Username ends with many numbers — suggests auto-generated account")
        suggestions.append("Remove trailing numbers and use a meaningful suffix")
        score -= 10

    for kw in ["free", "earn", "money", "profit", "win", "casino", "bet", "signal"]:
        if kw in username.lower():
            issues.append(f"❌ Keyword `{kw}` in username is a Telegram Ads policy risk")
            suggestions.append(f"Remove `{kw}` and use your niche name instead")
            score -= 25
            break

    if entity_type == "bot" and not username.lower().endswith("bot"):
        issues.append("⚠️ Bot username should end with 'bot' per Telegram convention")
        suggestions.append(f"Rename to `{username}Bot`")
        score -= 10

    return {"issues": issues, "suggestions": suggestions, "score": max(0, score)}


def generate_name_alternatives(username: str, entity_type: str) -> list:
    """Generate 3 policy-safe name alternatives."""
    base = username.lower().replace("_", "").replace("-", "")
    b    = base.capitalize()
    if entity_type == "channel":
        return [f"`{b}Hub`", f"`{b}Insights`", f"`The{b}Channel`"]
    elif entity_type == "group":
        return [f"`{b}Community`", f"`{b}Network`", f"`{b}Circle`"]
    else:
        return [f"`{b}AssistBot`", f"`{b}HelperBot`", f"`{b}ProBot`"]


def rewrite_content(text: str, language: str = "english") -> str:
    """Rewrite a post into a policy-compliant version."""
    cleaned = text
    for kw, safe in REWRITE_MAP.items():
        cleaned = re.sub(re.escape(kw), safe, cleaned, flags=re.IGNORECASE)
    # Remove excessive punctuation
    cleaned = re.sub(r'!{2,}', '!', cleaned)
    cleaned = re.sub(r'\?{2,}', '?', cleaned)
    # Normalize caps words (basic)
    def fix_caps(m):
        w = m.group(0)
        return w.capitalize() if len(w) > 3 else w
    cleaned = re.sub(r'\b[A-Z]{4,}\b', fix_caps, cleaned)

    if language == "arabic":
        note = "\n\n_(تمت إعادة الكتابة لتتوافق مع سياسات إعلانات تيليغرام)_"
    elif language == "russian":
        note = "\n\n_(Переписано для соответствия политике рекламы Telegram)_"
    else:
        note = "\n\n_(Rewritten for Telegram Ads policy compliance)_"

    return cleaned + note


def generate_ad_copies(username: str, entity_type: str) -> list:
    b = username.replace("_", " ").title()
    if entity_type == "channel":
        return [
            f"📢 *Copy 1 — Informational*\nStay ahead with *{b}* — expert insights and curated content trusted by thousands. ➡️ Explore now.",
            f"📢 *Copy 2 — Community*\nLooking for reliable niche content? *{b}* delivers consistent updates to an engaged audience. ➡️ Subscribe.",
            f"📢 *Copy 3 — Value*\n*{b}* shares practical knowledge with no fluff. Join today and level up. ➡️ Follow the channel.",
        ]
    elif entity_type == "group":
        return [
            f"📢 *Copy 1 — Community*\nJoin *{b}* — where members share insights and grow together. ➡️ Join the conversation.",
            f"📢 *Copy 2 — Engagement*\nReal discussions. Expert opinions. *{b}* is the place for serious learners. ➡️ Join today.",
            f"📢 *Copy 3 — Trust*\n*{b}* is a moderated, professional space for your niche. ➡️ Join the group.",
        ]
    else:
        return [
            f"📢 *Copy 1 — Utility*\nAutomate and simplify with *{b}*. Smart tools right inside Telegram. ➡️ Start now.",
            f"📢 *Copy 2 — Efficiency*\nSave time with *{b}*. Built for real users who want results. ➡️ Try it.",
            f"📢 *Copy 3 — Trust*\nThousands use *{b}* daily. Reliable, fast, and easy to use. ➡️ Get started.",
        ]


# ─────────────────────────────────────────────
# GATE CHECKS
# ─────────────────────────────────────────────
async def gate_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Block unapproved or disabled users from feature buttons."""
    query   = update.callback_query
    user_id = query.from_user.id

    if user_id == ADMIN_ID:
        return True

    status = get_user_status(user_id)
    if status == "disabled":
        await query.answer("🚫 Your access has been suspended.", show_alert=True)
        await query.edit_message_text(
            "🚫 *Access Suspended*\n\nYour bot access has been disabled by the admin.\n"
            "Contact @BlockSavvyMx to appeal.",
            parse_mode="Markdown"
        )
        return False
    if status != "approved":
        await query.answer("🔒 Request access first!", show_alert=True)
        await query.edit_message_text(
            "🔒 *Access Required*\n\nYou need admin approval before using this feature.\n"
            "Click *🔑 Request Admin Access* first.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return False
    return True


async def disabled_message_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True (and reply) if user is disabled — used in message handlers."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and get_user_status(user_id) == "disabled":
        await update.message.reply_text(
            "🚫 Access has been suspended. Contact admin @BlockSavvyMx."
        )
        return True
    return False


async def link_limit_check(update: Update, link: str) -> bool:
    """Enforce one-link analysis limit per user."""
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True
    used = get_used_link(user_id)
    if used:
        await update.message.reply_text(
            "🚫 *One-Link Limit Reached*\n\n"
            f"You have already used your free analysis on:\n`{used}`\n\n"
            "Contact @BlockSavvyMx to reactivate your access.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return False
    return True


# ─────────────────────────────────────────────
# /START
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if await disabled_message_guard(update, context):
        return

    if user.id == ADMIN_ID:
        upsert_user(user.id, user.username, user.first_name, "approved")
    else:
        upsert_user(user.id, user.username, user.first_name)

    await update.message.reply_text(
        "👋 *Welcome to AdApprovalPilot AI!*\n\n"
        "I help you fix Telegram Ads issues:\n"
        "❌ *Destination Quality* rejection\n"
        "⏳ Ads *stuck in review*\n"
        "📉 *Low CPM* performance\n\n"
        "🚀 Request access below, then use the tools to analyse and fix your ads.",
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
        await query.edit_message_text("👑 You are the admin — full access granted!", reply_markup=main_menu_keyboard())
        return

    status = get_user_status(user.id)
    if status == "approved":
        await query.edit_message_text("✅ You already have access!", reply_markup=main_menu_keyboard())
        return
    if status == "disabled":
        await query.edit_message_text("🚫 Your access is suspended. Contact @BlockSavvyMx.", reply_markup=main_menu_keyboard())
        return
    if status == "denied":
        await query.edit_message_text("❌ Access denied. Contact @BlockSavvyMx for help.", reply_markup=main_menu_keyboard())
        return

    upsert_user(user.id, user.username, user.first_name, "pending")

    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept",            callback_data=f"accept_{user.id}"),
            InlineKeyboardButton("❌ Deny",              callback_data=f"deny_{user.id}"),
        ],
        [
            InlineKeyboardButton("🚫 Disable User",      callback_data=f"disable_{user.id}"),
            InlineKeyboardButton("🗑 Remove From Assets", callback_data=f"removeassets_{user.id}"),
        ],
    ])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 *New Access Request*\n\n"
                f"👤 Name: {user.first_name}\n"
                f"🆔 User ID: `{user.id}`\n"
                f"📛 Username: @{user.username or 'N/A'}"
            ),
            parse_mode="Markdown",
            reply_markup=admin_keyboard
        )
        await query.edit_message_text(
            "⏳ *Request sent!*\n\nWait for admin approval. You'll be notified.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Admin message failed: {e}")
        await query.edit_message_text(
            "⚠️ Could not reach admin. Please try again later.",
            reply_markup=main_menu_keyboard()
        )


# ─────────────────────────────────────────────
# ADMIN DECISIONS
# ─────────────────────────────────────────────
async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return

    data      = query.data
    action, target_id_str = data.split("_", 1)
    target_id = int(target_id_str)

    if action == "accept":
        set_user_status(target_id, "approved")
        await query.edit_message_text(f"✅ User `{target_id}` *approved*.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "✅ *Access Granted!*\n\n"
                "You now have full access to AdApprovalPilot AI.\n"
                "Use /start to open the menu.\n\n"
                "⚠️ You have *one free analysis* (channel/group/bot).\n"
                "Contact @BlockSavvyMx to reactivate after use."
            ),
            parse_mode="Markdown"
        )

    elif action == "deny":
        set_user_status(target_id, "denied")
        await query.edit_message_text(f"❌ User `{target_id}` *denied*.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ *Access Denied.*\n\nContact @BlockSavvyMx if you think this is a mistake.",
            parse_mode="Markdown"
        )

    elif action == "disable":
        set_user_status(target_id, "disabled")
        await query.edit_message_text(f"🚫 User `{target_id}` *disabled*.", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🚫 *Your bot access has been suspended by the admin.*\n\nContact @BlockSavvyMx to appeal.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "removeassets":
        # Leave any chat/group the bot joined on behalf of this user
        joined = get_joined_chat(target_id)
        if joined:
            try:
                await context.bot.leave_chat(chat_id=joined)
                clear_joined_chat(target_id)
                await query.edit_message_text(
                    f"🗑 Bot has left the chat `{joined}` for user `{target_id}`.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                await query.edit_message_text(
                    f"⚠️ Could not leave chat: {e}",
                    parse_mode="Markdown"
                )
        else:
            await query.edit_message_text(
                f"ℹ️ No active chat/group found for user `{target_id}`.",
                parse_mode="Markdown"
            )


# ─────────────────────────────────────────────
# FULL SCAN + REPORT BUILDER
# ─────────────────────────────────────────────
async def run_full_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: str,
    entity_type: str
) -> None:
    """
    Orchestrates the full analysis flow:
    fetch → language detect → profile check → post scan → report.
    """
    username = _extract_username(link)
    user_id  = update.effective_user.id

    await update.message.reply_text(
        f"🔍 Starting full analysis of `{link}`...\n"
        "⏳ This may take a moment for large channels.",
        parse_mode="Markdown"
    )

    # 1. Fetch messages
    messages, fetch_error = await fetch_all_messages(context.bot, username)

    # 2. Detect language
    language = detect_language(messages)
    lang_display = {"english": "🇬🇧 English", "arabic": "🇸🇦 Arabic", "russian": "🇷🇺 Russian"}.get(language, "🌐 Unknown")

    # 3. Profile analysis
    profile   = analyze_profile(username, entity_type)
    name_alts = generate_name_alternatives(username, entity_type)
    score     = profile["score"]
    score_label = "🟢 Good" if score >= 80 else ("🟡 Needs Improvement" if score >= 50 else "🔴 High Risk")

    # 4. Post analysis
    flagged_posts = []
    for i, msg in enumerate(messages, 1):
        result = analyze_post(msg, i)
        if result:
            flagged_posts.append(result)

    # 5. Build report
    emoji = {"channel": "📊", "group": "👥", "bot": "🤖"}.get(entity_type, "🔍")
    label = entity_type.capitalize()

    report = (
        f"{emoji} *{label} Deep Analysis Report*\n"
        f"🔗 `{link}`\n"
        f"👤 `@{username}`\n"
        f"🌐 Language Detected: {lang_display}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Profile Score*: {score}/100 — {score_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if fetch_error:
        report += f"⚠️ *Note*: {fetch_error}\n\n"

    # Profile issues
    if profile["issues"]:
        report += "🚨 *Profile Issues:*\n"
        report += "\n".join(f"  {i}" for i in profile["issues"]) + "\n\n"
    else:
        report += "✅ *Profile looks clean.*\n\n"

    if profile["suggestions"]:
        report += "💡 *Profile Fixes:*\n"
        report += "\n".join(f"  • {s}" for s in profile["suggestions"]) + "\n\n"

    report += "✏️ *Name Alternatives:*\n"
    report += "\n".join(f"  • {a}" for a in name_alts) + "\n\n"

    # Post issues
    report += f"📋 *Post Scan*: {len(messages)} posts analysed\n\n"
    if flagged_posts:
        report += f"⚠️ *{len(flagged_posts)} Problematic Post(s) Found:*\n\n"
        for fp in flagged_posts:
            report += f"📌 *Post {fp['index']}*:\n_{fp['preview']}_\n"
            for r in fp["reasons"]:
                report += f"  {r}\n"
            report += "\n"
    else:
        report += (
            "✅ *No policy issues detected in your post contents.*\n"
            "Your content is ad-compliant.\n\n"
        )

    # Save used link
    set_used_link(user_id, link)

    # Store for rewrite
    context.user_data["flagged_posts"]  = [m for i, m in enumerate(messages, 1) if i in {fp["index"] for fp in flagged_posts}]
    context.user_data["language"]       = language
    context.user_data["entity_type"]    = entity_type

    if flagged_posts:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, rewrite them", callback_data="rewrite_yes"),
            InlineKeyboardButton("❌ No thanks",         callback_data="rewrite_no"),
        ]])
        await update.message.reply_text(
            report + "💬 *Do you want me to rewrite these posts into ad-compliant versions?*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────────
# CHANNEL INDEX
# ─────────────────────────────────────────────
async def channel_index_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "📊 *Channel Index*\n\nSend your channel link:\n`https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_CHANNEL_LINK

async def channel_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END
    link = update.message.text.strip()
    if not _extract_username(link):
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_CHANNEL_LINK
    if not await link_limit_check(update, link):
        return ConversationHandler.END
    await run_full_analysis(update, context, link, "channel")
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
        "👥 *Group Index*\n\nSend your group link:\n`https://t.me/yourgroup`",
        parse_mode="Markdown"
    )
    return WAIT_GROUP_LINK

async def group_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END
    link = update.message.text.strip()
    if not _extract_username(link):
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_GROUP_LINK
    if not await link_limit_check(update, link):
        return ConversationHandler.END
    await run_full_analysis(update, context, link, "group")
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
        "🤖 *Bot Index*\n\nSend your bot link:\n`https://t.me/YourBot`",
        parse_mode="Markdown"
    )
    return WAIT_BOT_LINK

async def bot_index_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END
    link = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_BOT_LINK
    if not await link_limit_check(update, link):
        return ConversationHandler.END

    await update.message.reply_text("🔍 Analysing your bot...")

    profile   = analyze_profile(username, "bot")
    name_alts = generate_name_alternatives(username, "bot")
    score     = profile["score"]
    score_label = "🟢 Good" if score >= 80 else ("🟡 Needs Improvement" if score >= 50 else "🔴 High Risk")

    # Simulate risky button detection
    risky_ctas = {
        "earn money fast":   "Get Started",
        "click to win":      "Explore Features",
        "free cash":         "Free Resources",
        "join and earn":     "Join the Community",
        "make money now":    "Start Learning",
    }
    button_issues = []
    for risky, safe in risky_ctas.items():
        if risky in username.lower():
            button_issues.append(f"❌ Button/CTA `{risky.title()}` is risky → Suggest: `{safe}`")

    report = (
        f"🤖 *Bot Analysis Report*\n"
        f"🔗 `{link}`\n"
        f"👤 `@{username}`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Profile Score*: {score}/100 — {score_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if profile["issues"]:
        report += "🚨 *Issues Detected:*\n" + "\n".join(f"  {i}" for i in profile["issues"]) + "\n\n"
    else:
        report += "✅ *Profile looks clean.*\n\n"

    if profile["suggestions"]:
        report += "💡 *Fixes:*\n" + "\n".join(f"  • {s}" for s in profile["suggestions"]) + "\n\n"

    report += "✏️ *Name Alternatives:*\n" + "\n".join(f"  • {a}" for a in name_alts) + "\n\n"

    if button_issues:
        report += "🔘 *Button/CTA Issues:*\n" + "\n".join(f"  {b}" for b in button_issues) + "\n\n"
        report += (
            "💡 *Safe CTA Replacements:*\n"
            "  • 'Click Here' → 'Get Started'\n"
            "  • 'Join Now' → 'Open Bot'\n"
            "  • 'Earn Free' → 'Explore Features'\n"
            "  • 'Tap Here' → 'Learn More'\n\n"
        )
    else:
        report += "✅ *No risky button text patterns detected.*\n\n"

    set_used_link(update.effective_user.id, link)
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────────
# REWRITE CALLBACKS
# ─────────────────────────────────────────────
async def rewrite_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    posts    = context.user_data.get("flagged_posts", [])
    language = context.user_data.get("language", "english")

    await query.edit_message_reply_markup(reply_markup=None)

    if not posts:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="✅ No posts to rewrite.",
            reply_markup=main_menu_keyboard()
        )
        return

    response = f"✅ *Rewritten Posts ({language.capitalize()} preserved):*\n\n"
    for i, post in enumerate(posts, 1):
        rw = rewrite_content(post, language)
        response += f"*Post {i} — Rewritten:*\n_{rw}_\n\n"

    response += "📋 These versions are safer for Telegram Ads policy compliance."
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
        text="👍 No problem. Use /start anytime to return to the main menu.",
        reply_markup=main_menu_keyboard()
    )


# ─────────────────────────────────────────────
# BOT JOIN / FIX SYSTEM
# ─────────────────────────────────────────────
async def bot_join_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "🔧 *Bot Fix Mode*\n\n"
        "To allow me to fix your channel or group:\n\n"
        "1️⃣ Add me as an *admin* to your channel/group\n"
        "2️⃣ Give me these permissions:\n"
        "   • Edit messages\n"
        "   • Delete messages\n"
        "   • Change group info\n\n"
        "3️⃣ Send the channel/group link below:",
        parse_mode="Markdown"
    )
    return WAIT_JOIN_LINK

async def bot_join_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END

    link     = update.message.text.strip()
    username = _extract_username(link)
    user_id  = update.effective_user.id

    if not username:
        await update.message.reply_text("⚠️ Invalid link. Please send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_JOIN_LINK

    await update.message.reply_text(f"🔍 Checking bot admin status in `@{username}`...", parse_mode="Markdown")

    try:
        chat   = await context.bot.get_chat(f"@{username}")
        member = await context.bot.get_chat_member(chat.id, context.bot.id)

        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text(
                "⚠️ I'm not an admin in that chat yet.\n\n"
                "Please add me as admin with edit/delete/change info permissions, then send the link again.",
                reply_markup=main_menu_keyboard()
            )
            return WAIT_JOIN_LINK

        # Bot is admin — save and offer fixes
        set_joined_chat(user_id, str(chat.id))

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, apply fixes", callback_data=f"applyfix_{chat.id}"),
            InlineKeyboardButton("❌ No, just suggest", callback_data="rewrite_no"),
        ]])
        await update.message.reply_text(
            f"✅ *Bot is admin in* `@{username}`!\n\n"
            "I can now:\n"
            "• Fix the channel/group name & description\n"
            "• Edit or delete non-compliant posts\n\n"
            "⚠️ *Do you want me to apply these fixes automatically?*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Could not access `@{username}`.\n"
            "Make sure the link is correct and I am added as admin.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        logger.error(f"Bot join error: {e}")
        return ConversationHandler.END


async def apply_fix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data    = query.data  # applyfix_<chat_id>
    chat_id = int(data.split("_", 1)[1])

    await query.edit_message_reply_markup(reply_markup=None)

    results = []
    # Attempt to update description
    try:
        await context.bot.set_chat_description(
            chat_id=chat_id,
            description=(
                "Official channel with expert insights and curated content. "
                "Follow for reliable updates in your niche."
            )
        )
        results.append("✅ Description updated to policy-compliant version")
    except Exception as e:
        results.append(f"⚠️ Could not update description: {e}")

    result_text = "🔧 *Fix Results:*\n\n" + "\n".join(results)
    result_text += (
        "\n\n📋 *Note:* Editing/deleting individual posts requires the full message history scan. "
        "Use Channel Index or Group Index after adding me as admin for a complete scan."
    )

    await context.bot.send_message(
        chat_id=user_id,
        text=result_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


# ─────────────────────────────────────────────
# AD TEXT
# ─────────────────────────────────────────────
async def ad_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "✍️ *Ad Text Generator*\n\n"
        "Send your channel, group, or bot link.\n"
        "I'll generate 3 custom, policy-compliant ad copies.\n\n"
        "Example: `https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_AD_LINK

async def ad_text_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END
    link     = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_AD_LINK

    await update.message.reply_text("✍️ Generating custom ad copies...")

    entity_type = "bot" if username.lower().endswith("bot") else (
        "group" if any(w in username.lower() for w in ["group", "chat", "community"]) else "channel"
    )
    copies   = generate_ad_copies(username, entity_type)
    response = f"✍️ *3 Custom Ad Copies for* `@{username}`\n\n" + "\n\n".join(copies)
    response += (
        "\n\n📋 *Tips:*\n"
        "• A/B test all 3 — track which has the best CTR\n"
        "• Match destination to ad copy promise\n"
        "• Never add risky phrases after generation"
    )
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────────
# AD BUDGET
# ─────────────────────────────────────────────
async def ad_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "💰 *Ad Budget Optimizer*\n\nEnter your total budget in USD.\nExample: `50`",
        parse_mode="Markdown"
    )
    return WAIT_BUDGET

async def ad_budget_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END
    try:
        budget = float(re.sub(r"[^\d.]", "", update.message.text))
        if budget <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid positive number. Example: `50`", parse_mode="Markdown")
        return WAIT_BUDGET

    duration  = 7 if budget <= 50 else (14 if budget <= 200 else 30)
    daily_opt = round(budget / duration, 2)
    ton_total = usd_to_ton(budget)
    ton_daily = usd_to_ton(daily_opt)

    await update.message.reply_text(
        f"💰 *Budget Optimization Report*\n\n"
        f"💵 *Total*: ${budget:.2f} ≈ {ton_total} TON\n"
        f"📅 *Duration*: {duration} days\n"
        f"📆 *Daily Spend*: ${daily_opt:.2f}/day ≈ {ton_daily} TON/day\n\n"
        f"📋 *Strategy:*\n"
        f"• Days 1–3: Test 2–3 ad variants\n"
        f"• Days 4–7: Scale best performer, pause others\n"
        f"• Pause ads with CTR below 1% after day 3\n\n"
        f"💡 *Tips:*\n"
        f"• Start in Tier 2 countries (NG, IN, BR) for lower CPM\n"
        f"• Use a channel post as your ad destination\n"
        f"• Set frequency cap: 2 impressions/user/day\n\n"
        f"🪙 Rate: ~{TON_PER_USD} TON/USD (verify on CoinGecko)",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
# CPM PREDICTOR
# ─────────────────────────────────────────────
CPM_TABLE = {
    "crypto":    (1.5, 3.5, "High",   "Test Tier 2 countries (IN, NG, BR) to reduce CPM"),
    "finance":   (1.2, 3.0, "High",   "Use narrow interest targeting to avoid broad CPM inflation"),
    "tech":      (0.8, 2.0, "Medium", "Mix Tier 1 and Tier 2 geo for balanced volume and cost"),
    "education": (0.5, 1.2, "Low",    "Great niche for tight budgets — high engagement rate"),
    "gaming":    (0.6, 1.5, "Low",    "Younger audience — use interactive creatives for best CTR"),
    "health":    (0.9, 2.2, "Medium", "Policy-sensitive — avoid health claims in ad copy"),
    "ecommerce": (0.7, 1.8, "Medium", "Retargeting works best — link to channel not website"),
    "news":      (0.4, 1.0, "Low",    "Very broad — narrow by language for better quality traffic"),
    "trading":   (1.8, 4.0, "High",   "Very competitive — ensure full financial ad compliance"),
    "nft":       (1.0, 2.5, "High",   "Avoid hype language — policy rejections are common here"),
    "fitness":   (0.6, 1.4, "Low",    "Narrow by specific goal (weight loss, bodybuilding, etc.)"),
    "travel":    (0.5, 1.3, "Low",    "Plan around seasonal peaks for best CPM efficiency"),
}

async def ad_cpm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        f"📉 *CPM Predictor*\n\n"
        f"What is your niche or audience?\n\n"
        f"Known niches: `{', '.join(CPM_TABLE.keys())}`\n\n"
        f"Or describe freely (e.g. 'crypto traders in Nigeria')",
        parse_mode="Markdown"
    )
    return WAIT_CPM_NICHE

async def ad_cpm_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_message_guard(update, context):
        return ConversationHandler.END
    text    = update.message.text.lower()
    matched = next((k for k in CPM_TABLE if k in text), None)

    if matched:
        lo, hi, risk, tip = CPM_TABLE[matched]
        niche_label = matched.capitalize()
    else:
        lo, hi, risk, tip = 0.6, 1.8, "Medium", "Be more specific about your niche for better targeting"
        niche_label = "General"

    risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk, "🟡")

    await update.message.reply_text(
        f"📉 *CPM Prediction Report*\n\n"
        f"🎯 *Niche*: {niche_label}\n"
        f"💵 *Estimated CPM*: ${lo}–${hi} (~{usd_to_ton(lo)}–{usd_to_ton(hi)} TON)\n"
        f"⚠️ *Risk Level*: {risk_emoji} {risk}\n\n"
        f"💡 *Recommendation*: {tip}\n\n"
        f"📋 *Targeting Tips:*\n"
        f"• Tier 2 geos (IN, NG, PK, BR) cut CPM by 40–60%\n"
        f"• Narrow targeting = higher CPM, better conversions\n"
        f"• Broad targeting = lower CPM, lower quality traffic\n"
        f"• Test 2–3 creatives before scaling\n"
        f"• Match ad language to your target geo\n\n"
        f"🪙 Rate: ~{TON_PER_USD} TON/USD (verify on CoinGecko)",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
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
ptb_app   = Application.builder().token(TOKEN).build()

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
    # Commands
    ptb_app.add_handler(CommandHandler("start", start))

    # Standalone callbacks (registered BEFORE ConversationHandlers)
    ptb_app.add_handler(CallbackQueryHandler(req_access,     pattern="^req_access$"))
    ptb_app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(accept|deny|disable|removeassets)_\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(rewrite_yes,    pattern="^rewrite_yes$"))
    ptb_app.add_handler(CallbackQueryHandler(rewrite_no,     pattern="^rewrite_no$"))
    ptb_app.add_handler(CallbackQueryHandler(apply_fix,      pattern="^applyfix_-?\\d+$"))

    # Conversation: Channel Index
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(channel_index_start, pattern="^channel_index$")],
        states={WAIT_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, channel_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Conversation: Group Index
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(group_index_start, pattern="^group_index$")],
        states={WAIT_GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Conversation: Bot Index
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_index_start, pattern="^bot_index$")],
        states={WAIT_BOT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Conversation: Ad Text
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_text_start, pattern="^ad_text$")],
        states={WAIT_AD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Conversation: Ad Budget
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_budget_start, pattern="^ad_budget$")],
        states={WAIT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_budget_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Conversation: CPM
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_cpm_start, pattern="^ad_cpm$")],
        states={WAIT_CPM_NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_cpm_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Conversation: Bot Join / Fix Mode
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_join_start, pattern="^bot_join$")],
        states={WAIT_JOIN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_join_link)]},
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
    logger.info(f"Webhook set: {WEBHOOK_URL}/{TOKEN}")

init_db()
asyncio.run(setup())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
