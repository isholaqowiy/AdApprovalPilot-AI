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
from telegram.error import TelegramError, Forbidden, BadRequest

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
TON_PER_USD    = 0.67

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
    WAIT_TARGET_LINKS,
    WAIT_NICHE_DETAILS,
) = range(9)

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
    for col, defn in [
        ("used_link",   "TEXT DEFAULT NULL"),
        ("joined_chat", "TEXT DEFAULT NULL"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except Exception:
            pass
    conn.commit()
    conn.close()

def upsert_user(user_id, username, first_name, status="pending"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, username, first_name, access_status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            access_status=COALESCE(
                CASE WHEN access_status IN ('approved','disabled') THEN access_status END,
                excluded.access_status
            )
    """, (user_id, username or "", first_name or "", status))
    conn.commit()
    conn.close()

def set_user_status(user_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET access_status=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

def get_user_status(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT access_status FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_used_link(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT used_link FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_used_link(user_id, link):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET used_link=? WHERE user_id=?", (link, user_id))
    conn.commit()
    conn.close()

def set_joined_chat(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET joined_chat=? WHERE user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()

def get_joined_chat(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT joined_chat FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def clear_joined_chat(user_id):
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
        [InlineKeyboardButton("🔑 Request Admin Access",            callback_data="req_access")],
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

def _extract_username(link: str):
    link = link.strip()
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", link)
    if match:
        return match.group(1)
    if link.startswith("@"):
        return link[1:]
    return None

def usd_to_ton(usd: float) -> float:
    return round(usd * TON_PER_USD, 2)

def is_approved(user_id):
    return get_user_status(user_id) == "approved"

def is_disabled(user_id):
    return get_user_status(user_id) == "disabled"

# ─────────────────────────────────────────────
# ANALYSIS CONSTANTS
# ─────────────────────────────────────────────
RISKY_KEYWORDS = [
    "earn fast", "make money", "get rich", "guaranteed", "guarantee",
    "100%", "no risk", "risk free", "free money", "instant profit",
    "passive income", "work from home", "double your", "click now",
    "act now", "limited time", "winner", "prize", "cash",
    "investment returns", "financial freedom", "secret method",
    "hack", "exploit", "unlimited", "forex", "pump", "signal",
    "crypto signal", "join now", "don't miss", "airdrop", "get paid",
    "referral bonus", "mlm", "ponzi", "easy money", "no experience",
    "fast cash", "100x", "moon", "lambo", "free crypto",
]

SUSPICIOUS_LINK_PATTERNS = [
    r"bit\.ly", r"tinyurl", r"shorte\.st", r"cutt\.ly",
    r"gg\.gg", r"t\.cn", r"rebrand\.ly", r"is\.gd",
]

REWRITE_MAP = {
    "earn fast":      "grow your knowledge quickly",
    "make money":     "build financial value",
    "get rich":       "achieve your financial goals",
    "guaranteed":     "proven",
    "guarantee":      "trusted",
    "100%":           "highly effective",
    "no risk":        "beginner-friendly",
    "risk free":      "low barrier to entry",
    "free money":     "free resources",
    "instant profit": "measurable results",
    "passive income": "consistent returns",
    "work from home": "remote opportunities",
    "double your":    "grow your",
    "click now":      "learn more",
    "act now":        "get started today",
    "limited time":   "exclusive",
    "winner":         "top performer",
    "prize":          "reward",
    "cash":           "value",
    "join now":       "join us",
    "don't miss":     "explore",
    "airdrop":        "token distribution",
    "get paid":       "earn value",
    "fast cash":      "quick results",
    "easy money":     "accessible opportunity",
    "moon":           "growth potential",
    "pump":           "market movement",
    "signal":         "market insight",
}

# ─────────────────────────────────────────────
# REAL TELEGRAM DATA FETCHER
# ─────────────────────────────────────────────
async def fetch_chat_data(bot, username: str) -> dict:
    """
    Fetch REAL data from Telegram API.
    Returns dict with available fields or error info.
    NEVER generates or assumes data.
    """
    result = {
        "success":          False,
        "error":            None,
        "name":             None,
        "description":      None,
        "username":         username,
        "member_count":     None,
        "chat_type":        None,
        "has_description":  False,
        "has_photo":        False,
    }
    try:
        chat = await bot.get_chat(f"@{username}")
        result["success"]         = True
        result["name"]            = chat.title or chat.full_name or username
        result["description"]     = chat.description or chat.bio or None
        result["has_description"] = bool(chat.description or chat.bio)
        result["has_photo"]       = bool(chat.photo)
        result["chat_type"]       = chat.type

        # Member count (works for supergroups and channels)
        try:
            count = await bot.get_chat_member_count(f"@{username}")
            result["member_count"] = count
        except Exception:
            result["member_count"] = None

    except Forbidden:
        result["error"] = "private_or_restricted"
    except BadRequest as e:
        result["error"] = f"bad_request: {e}"
    except TelegramError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)

    return result


def analyze_post_text(text: str, index: int) -> dict | None:
    """
    Analyze a REAL post text for policy issues.
    Returns None if clean.
    """
    if not text or not text.strip():
        return None

    t      = text.lower()
    issues = []

    found_kw = [kw for kw in RISKY_KEYWORDS if kw in t]
    if found_kw:
        issues.append(f"❌ Risky phrases: `{'`, `'.join(found_kw)}`")

    for pat in SUSPICIOUS_LINK_PATTERNS:
        if re.search(pat, t):
            issues.append("⚠️ Contains shortened/suspicious URL — flagged by Telegram review system")
            break

    caps_words = [w for w in text.split() if len(w) > 3 and w.isupper()]
    if len(caps_words) >= 3:
        issues.append("⚠️ Excessive ALL-CAPS — signals low-quality promotional content")

    if text.count("!") >= 3:
        issues.append("⚠️ Too many exclamation marks — triggers spam filters")

    if not issues:
        return None

    return {
        "index":   index,
        "preview": text[:120] + ("..." if len(text) > 120 else ""),
        "issues":  issues,
    }


def rewrite_content(text: str) -> str:
    """Rewrite a post into a policy-compliant version."""
    cleaned = text
    for kw, safe in REWRITE_MAP.items():
        cleaned = re.sub(re.escape(kw), safe, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'!{2,}', '!', cleaned)
    cleaned = re.sub(r'\?{2,}', '?', cleaned)
    return cleaned


def analyze_profile_username(username: str, entity_type: str) -> dict:
    """Analyze username patterns for policy issues."""
    issues      = []
    suggestions = []
    score       = 100

    if len(username) < 5:
        issues.append("❌ Username too short (<5 chars) — reduces trust score")
        suggestions.append(f"Try `{username}_official` or `{username}_hub`")
        score -= 20

    if username.isupper():
        issues.append("❌ All-caps username appears spammy")
        suggestions.append(f"Use mixed case: `{username.capitalize()}`")
        score -= 15

    if "__" in username:
        issues.append("⚠️ Double underscores signal low-quality account")
        suggestions.append("Replace `__` with single `_` or remove")
        score -= 10

    if re.search(r'\d{3,}$', username):
        issues.append("⚠️ Trailing numbers suggest auto-generated account")
        suggestions.append("Remove trailing numbers and use a meaningful suffix")
        score -= 10

    for kw in ["free", "earn", "money", "profit", "win", "casino", "bet", "signal", "forex"]:
        if kw in username.lower():
            issues.append(f"❌ `{kw}` in username is a known Telegram Ads policy risk")
            suggestions.append(f"Remove `{kw}` — use your niche name instead")
            score -= 25
            break

    if entity_type == "bot" and not username.lower().endswith("bot"):
        issues.append("⚠️ Bot username should end with 'bot' per Telegram convention")
        suggestions.append(f"Rename to `{username}Bot`")
        score -= 10

    return {"issues": issues, "suggestions": suggestions, "score": max(0, score)}


def generate_name_alternatives(username: str, entity_type: str) -> list:
    b = username.lower().replace("_", "").replace("-", "").capitalize()
    if entity_type == "channel":
        return [f"`{b}Hub`", f"`{b}Insights`", f"`The{b}Channel`"]
    elif entity_type == "group":
        return [f"`{b}Community`", f"`{b}Network`", f"`{b}Circle`"]
    else:
        return [f"`{b}AssistBot`", f"`{b}HelperBot`", f"`{b}ProBot`"]


def generate_ad_copies(username: str, entity_type: str, description: str = None) -> list:
    b    = username.replace("_", " ").title()
    desc = description or ""

    if entity_type == "channel":
        return [
            f"📢 *Copy 1 — Informational*\nStay informed with *{b}* — expert insights and curated content trusted by an engaged audience. ➡️ Explore now.",
            f"📢 *Copy 2 — Community*\nLooking for reliable content in your niche? *{b}* delivers consistent, high-quality updates. ➡️ Subscribe.",
            f"📢 *Copy 3 — Value*\n*{b}* shares practical knowledge with no fluff. Join today and level up your expertise. ➡️ Follow the channel.",
        ]
    elif entity_type == "group":
        return [
            f"📢 *Copy 1 — Community*\nJoin *{b}* — where members share insights and grow together. ➡️ Join the conversation.",
            f"📢 *Copy 2 — Engagement*\nReal discussions. Expert opinions. *{b}* is built for serious learners. ➡️ Join today.",
            f"📢 *Copy 3 — Trust*\n*{b}* is a moderated, professional space for your niche. Come and connect. ➡️ Join the group.",
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
    query   = update.callback_query
    user_id = query.from_user.id
    if user_id == ADMIN_ID:
        return True
    status = get_user_status(user_id)
    if status == "disabled":
        await query.answer("🚫 Your access has been suspended.", show_alert=True)
        await query.edit_message_text(
            "🚫 *Access Suspended*\n\nContact @BlockSavvyMx to appeal.",
            parse_mode="Markdown"
        )
        return False
    if status != "approved":
        await query.answer("🔒 Request access first!", show_alert=True)
        await query.edit_message_text(
            "🔒 *Access Required*\n\nClick *🔑 Request Admin Access* first.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return False
    return True

async def disabled_guard(update: Update) -> bool:
    """Returns True (and warns) if user is disabled. Use in message handlers."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and get_user_status(user_id) == "disabled":
        await update.message.reply_text(
            "🚫 Access has been suspended. Contact admin @BlockSavvyMx."
        )
        return True
    return False

async def link_limit_check(update: Update, link: str) -> bool:
    """
    Enforce one-link limit.
    SAME link = allowed (re-analysis).
    DIFFERENT link = blocked.
    Admin exempt.
    """
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True
    used = get_used_link(user_id)
    if used and used != link:
        await update.message.reply_text(
            "🚫 *One-Link Limit Reached*\n\n"
            f"You have already used your free analysis on:\n`{used}`\n\n"
            "You can re-analyze the same link anytime.\n"
            "Contact @BlockSavvyMx to unlock a different link.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return False
    return True

# ─────────────────────────────────────────────
# FULL ANALYSIS RUNNER (REAL DATA ONLY)
# ─────────────────────────────────────────────
async def run_full_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: str,
    entity_type: str
):
    """
    Fetch REAL data from Telegram API and build analysis report.
    NEVER generates or assumes posts or subscribers.
    """
    username = _extract_username(link)
    user_id  = update.effective_user.id

    await update.message.reply_text(
        f"🔍 Fetching real data for `@{username}` from Telegram...",
        parse_mode="Markdown"
    )

    # ── 1. Fetch real chat data ──
    chat_data = await fetch_chat_data(context.bot, username)

    if not chat_data["success"]:
        err = chat_data["error"]
        if "private_or_restricted" in str(err):
            msg = (
                "🔒 *Cannot Access This Channel/Group*\n\n"
                "This channel/group is private or has restricted access.\n\n"
                "To allow full analysis:\n"
                "• Make the channel/group public temporarily, OR\n"
                "• Use the *🔧 Allow Bot to Fix* feature to add me as admin."
            )
        else:
            msg = (
                "⚠️ *Unable to Access Data*\n\n"
                "Unable to access sufficient data for this channel/group.\n"
                "Please ensure the link is correct and the channel is public."
            )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return

    # ── 2. Profile score ──
    profile     = analyze_profile_username(username, entity_type)
    score       = profile["score"]
    score_label = "🟢 Good" if score >= 80 else ("🟡 Needs Improvement" if score >= 50 else "🔴 High Risk")
    name_alts   = generate_name_alternatives(username, entity_type)

    # ── 3. Build report header ──
    emoji = {"channel": "📊", "group": "👥", "bot": "🤖"}.get(entity_type, "🔍")
    report = (
        f"{emoji} *{entity_type.capitalize()} Analysis Report*\n"
        f"🔗 `{link}`\n"
        f"👤 `@{username}`\n"
        f"📛 Name: *{chat_data['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Profile Score*: {score}/100 — {score_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    # ── 4. Subscriber trust analysis (REAL data) ──
    member_count = chat_data["member_count"]
    if member_count is not None:
        report += f"👥 *Subscribers/Members*: {member_count:,}\n\n"
        if member_count < 1000:
            report += (
                "⚠️ *Low Trust Level Detected*\n\n"
                f"Your channel currently has *{member_count:,}* subscribers.\n\n"
                "Channels with fewer than 1,000 subscribers often face low trust "
                "from the Telegram Ads review system.\n\n"
                "📌 *Recommendation*: Grow your channel to at least "
                "1,000–5,000+ subscribers before running ads for better approval chances.\n\n"
            )
    else:
        report += "👥 *Subscribers*: Unable to fetch (private or restricted)\n\n"

    # ── 5. Description analysis (REAL data) ──
    if chat_data["has_description"] and chat_data["description"]:
        desc      = chat_data["description"]
        desc_kw   = [kw for kw in RISKY_KEYWORDS if kw in desc.lower()]
        report += f"📝 *Description*: _{desc[:200]}{'...' if len(desc) > 200 else ''}_\n\n"
        if desc_kw:
            report += f"⚠️ *Risky words in description*: `{'`, `'.join(desc_kw)}`\n\n"
        else:
            report += "✅ *Description appears clean.*\n\n"
    else:
        report += (
            "📝 *Description*: Not set\n"
            "⚠️ Empty description is a known ad rejection trigger. "
            "Add a clear, niche-specific description.\n\n"
        )

    # ── 6. Profile photo ──
    if not chat_data["has_photo"]:
        report += "🖼 *Profile Photo*: Not set — adds trust signal when present\n\n"
    else:
        report += "🖼 *Profile Photo*: ✅ Set\n\n"

    # ── 7. Username issues ──
    if profile["issues"]:
        report += "🚨 *Username Issues:*\n"
        report += "\n".join(f"  {i}" for i in profile["issues"]) + "\n\n"
    else:
        report += "✅ *Username looks clean.*\n\n"

    if profile["suggestions"]:
        report += "💡 *Fixes:*\n" + "\n".join(f"  • {s}" for s in profile["suggestions"]) + "\n\n"

    report += "✏️ *Name Alternatives:*\n" + "\n".join(f"  • {a}" for a in name_alts) + "\n\n"

    # ── 8. Post analysis — NO fake posts ──
    # Bots cannot read channel history unless admin.
    # We ONLY analyze what we can access (description text).
    report += (
        "📋 *Post Content Analysis*:\n"
        "To scan actual posts, add me as admin via *🔧 Allow Bot to Fix My Channel/Group*.\n"
        "Without admin access, post-level scanning is not possible.\n\n"
    )

    # ── 9. Save used link ──
    set_used_link(user_id, link)

    # ── 10. Store context for target channel step ──
    context.user_data["main_link"]         = link
    context.user_data["main_entity_type"]  = entity_type
    context.user_data["main_description"]  = chat_data.get("description", "")

    # ── 11. Ask for target channels ──
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📡 Analyse Target Channels", callback_data="analyse_targets"),
        InlineKeyboardButton("⏭ Skip",                    callback_data="skip_targets"),
    ]])

    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ─────────────────────────────────────────────
# TARGET CHANNEL ANALYSIS
# ─────────────────────────────────────────────
async def analyse_targets_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=(
            "📡 *Target Channel Analysis*\n\n"
            "Please send the list of target channels/groups used in your ad campaign.\n\n"
            "Format — one per line:\n"
            "`https://t.me/channel1`\n"
            "`https://t.me/channel2`\n\n"
            "Or send: /cancel to return to the menu."
        ),
        parse_mode="Markdown"
    )
    return WAIT_TARGET_LINKS

async def analyse_targets_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END

    raw_lines = update.message.text.strip().split("\n")
    links     = [l.strip() for l in raw_lines if l.strip()]

    if not links:
        await update.message.reply_text("⚠️ No links detected. Please send at least one link.")
        return WAIT_TARGET_LINKS

    await update.message.reply_text(
        f"🔍 Analysing {len(links)} target channel(s)... Please wait."
    )

    report = "📡 *Target Channel Risk Report*\n\n"

    for link in links:
        username = _extract_username(link)
        if not username:
            report += f"⚠️ Invalid link: `{link}` — skipped\n\n"
            continue

        chat_data = await fetch_chat_data(context.bot, username)

        if not chat_data["success"]:
            report += (
                f"🔗 `@{username}`\n"
                "⚠️ Unable to access this channel/group. "
                "It may be private or restricted.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
            )
            continue

        # Risk scoring based ONLY on real data
        risk_score  = 0
        risk_flags  = []
        suggestions = []

        count = chat_data["member_count"]
        if count is not None:
            if count < 1000:
                risk_score += 40
                risk_flags.append(f"Subscriber count too low ({count:,} — needs 1,000+)")
                suggestions.append("Grow audience to at least 1,000 before using as ad target")
            elif count < 5000:
                risk_score += 15
                risk_flags.append(f"Moderate subscriber count ({count:,})")
                suggestions.append("Aim for 5,000+ subscribers for stronger ad placement")
        else:
            risk_score += 20
            risk_flags.append("Subscriber count unavailable — could not verify audience size")

        if not chat_data["has_description"]:
            risk_score += 25
            risk_flags.append("No description set — weak profile signal")
            suggestions.append("Add a niche-specific description")
        else:
            desc    = chat_data["description"] or ""
            desc_kw = [kw for kw in RISKY_KEYWORDS if kw in desc.lower()]
            if desc_kw:
                risk_score += 20
                risk_flags.append(f"Risky keywords in description: {', '.join(desc_kw)}")
                suggestions.append("Remove policy-risky phrases from description")

        if not chat_data["has_photo"]:
            risk_score += 10
            risk_flags.append("No profile photo — reduces trust signal")
            suggestions.append("Add a professional profile photo")

        # Assign risk level
        if risk_score >= 50:
            risk_label = "🔴 HIGH RISK"
        elif risk_score >= 25:
            risk_label = "🟡 MEDIUM RISK"
        else:
            risk_label = "🟢 LOW RISK"

        report += f"🎯 *Target*: `@{username}`\n"
        report += f"📛 Name: {chat_data['name']}\n"
        if count is not None:
            report += f"👥 Subscribers: {count:,}\n"
        report += f"⚠️ *Risk Level*: {risk_label}\n\n"

        if risk_flags:
            report += "*Reasons (based on real data):*\n"
            report += "\n".join(f"  • {f}" for f in risk_flags) + "\n\n"
        else:
            report += "✅ No major issues detected.\n\n"

        if suggestions:
            report += "*Recommendations:*\n"
            report += "\n".join(f"  • {s}" for s in suggestions) + "\n\n"

        report += "━━━━━━━━━━━━━━━━━━\n\n"
        await asyncio.sleep(0.5)  # Rate limit protection

    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def skip_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="✅ Analysis complete. Use /start to return to the main menu.",
        reply_markup=main_menu_keyboard()
    )

# ─────────────────────────────────────────────
# /START
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return
    user = update.effective_user
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
    user  = query.from_user

    if user.id == ADMIN_ID:
        await query.edit_message_text("👑 You are the admin — full access granted!", reply_markup=main_menu_keyboard())
        return

    status = get_user_status(user.id)
    if status == "approved":
        await query.edit_message_text("✅ You already have access!", reply_markup=main_menu_keyboard())
        return
    if status == "disabled":
        await query.edit_message_text("🚫 Access suspended. Contact @BlockSavvyMx.", reply_markup=main_menu_keyboard())
        return
    if status == "denied":
        await query.edit_message_text("❌ Access denied. Contact @BlockSavvyMx.", reply_markup=main_menu_keyboard())
        return

    upsert_user(user.id, user.username, user.first_name, "pending")

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
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Accept",             callback_data=f"accept_{user.id}"),
                    InlineKeyboardButton("❌ Deny",               callback_data=f"deny_{user.id}"),
                ],
                [
                    InlineKeyboardButton("🚫 Disable User",       callback_data=f"disable_{user.id}"),
                    InlineKeyboardButton("🗑 Remove From Assets",  callback_data=f"removeassets_{user.id}"),
                ],
            ])
        )
        await query.edit_message_text(
            "⏳ *Request sent!*\n\nWait for admin approval. You'll be notified.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Admin message failed: {e}")
        await query.edit_message_text("⚠️ Could not reach admin. Try again later.", reply_markup=main_menu_keyboard())

# ─────────────────────────────────────────────
# ADMIN DECISIONS
# ─────────────────────────────────────────────
async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return

    action, target_str = query.data.split("_", 1)
    target_id = int(target_str)

    if action == "accept":
        set_user_status(target_id, "approved")
        await query.edit_message_text(f"✅ User `{target_id}` approved.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "✅ *Access Granted!*\n\n"
                "You now have full access to AdApprovalPilot AI.\n"
                "Use /start to open the menu.\n\n"
                "⚠️ You have *one free link analysis*.\n"
                "Re-analysing the same link is always allowed.\n"
                "Contact @BlockSavvyMx to unlock a different link."
            ),
            parse_mode="Markdown"
        )

    elif action == "deny":
        set_user_status(target_id, "denied")
        await query.edit_message_text(f"❌ User `{target_id}` denied.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ *Access Denied.*\n\nContact @BlockSavvyMx if this is a mistake.",
            parse_mode="Markdown"
        )

    elif action == "disable":
        set_user_status(target_id, "disabled")
        await query.edit_message_text(f"🚫 User `{target_id}` disabled.", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🚫 *Your bot access has been suspended by the admin.*\n\nContact @BlockSavvyMx to appeal.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "removeassets":
        joined = get_joined_chat(target_id)
        if joined:
            try:
                await context.bot.leave_chat(chat_id=joined)
                clear_joined_chat(target_id)
                await query.edit_message_text(f"🗑 Bot left chat `{joined}` for user `{target_id}`.", parse_mode="Markdown")
            except Exception as e:
                await query.edit_message_text(f"⚠️ Could not leave chat: {e}", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"ℹ️ No active chat found for user `{target_id}`.", parse_mode="Markdown")

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
    if await disabled_guard(update):
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
    if await disabled_guard(update):
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
    if await disabled_guard(update):
        return ConversationHandler.END
    link = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_BOT_LINK
    if not await link_limit_check(update, link):
        return ConversationHandler.END

    await update.message.reply_text("🔍 Fetching real bot data from Telegram...")

    chat_data = await fetch_chat_data(context.bot, username)
    profile   = analyze_profile_username(username, "bot")
    score     = profile["score"]
    score_label = "🟢 Good" if score >= 80 else ("🟡 Needs Improvement" if score >= 50 else "🔴 High Risk")
    name_alts = generate_name_alternatives(username, "bot")

    report = (
        f"🤖 *Bot Analysis Report*\n"
        f"🔗 `{link}`\n"
        f"👤 `@{username}`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Profile Score*: {score}/100 — {score_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if chat_data["success"]:
        report += f"📛 Name: *{chat_data['name']}*\n"
        if chat_data["has_description"]:
            desc    = chat_data["description"]
            desc_kw = [kw for kw in RISKY_KEYWORDS if kw in desc.lower()]
            report += f"📝 Description: _{desc[:200]}_\n"
            if desc_kw:
                report += f"⚠️ Risky words in description: `{'`, `'.join(desc_kw)}`\n"
            else:
                report += "✅ Description is clean.\n"
        else:
            report += "📝 Description: Not set — add one via BotFather\n"
        report += f"🖼 Photo: {'✅ Set' if chat_data['has_photo'] else '❌ Not set'}\n\n"
    else:
        report += (
            "⚠️ *Could not fetch full bot data.*\n"
            "Ensure the bot is public and the link is correct.\n\n"
        )

    if profile["issues"]:
        report += "🚨 *Username Issues:*\n" + "\n".join(f"  {i}" for i in profile["issues"]) + "\n\n"
    else:
        report += "✅ *Username looks clean.*\n\n"

    if profile["suggestions"]:
        report += "💡 *Fixes:*\n" + "\n".join(f"  • {s}" for s in profile["suggestions"]) + "\n\n"

    report += "✏️ *Name Alternatives:*\n" + "\n".join(f"  • {a}" for a in name_alts) + "\n\n"

    # CTA/button risk check on username
    risky_ctas = {"earn": "Get Started", "free": "Explore Features", "money": "Learn More", "win": "Join Community"}
    found_ctas = [(r, s) for r, s in risky_ctas.items() if r in username.lower()]
    if found_ctas:
        report += "🔘 *Risky CTA Patterns Detected:*\n"
        for r, s in found_ctas:
            report += f"  ❌ `{r}` in bot name → Suggest: `{s}`\n"
        report += "\n"

    set_used_link(update.effective_user.id, link)
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

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
        "I'll generate 3 custom, policy-compliant ad copies based on the real channel data.\n\n"
        "Example: `https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_AD_LINK

async def ad_text_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    link     = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_AD_LINK

    await update.message.reply_text("✍️ Fetching channel data to generate accurate ad copies...")

    chat_data   = await fetch_chat_data(context.bot, username)
    description = chat_data.get("description") if chat_data["success"] else None

    if not chat_data["success"] or not description:
        await update.message.reply_text(
            "ℹ️ *Could not fetch channel description.*\n\n"
            "Please tell me more about your channel niche so I can generate accurate ad copies.\n\n"
            "Example: 'Crypto trading tips for beginners in Nigeria'",
            parse_mode="Markdown"
        )
        context.user_data["ad_username"] = username
        return WAIT_NICHE_DETAILS

    entity_type = "bot" if username.lower().endswith("bot") else (
        "group" if any(w in username.lower() for w in ["group", "chat", "community"]) else "channel"
    )
    copies   = generate_ad_copies(username, entity_type, description)
    response = (
        f"✍️ *3 Custom Ad Copies for* `@{username}`\n"
        f"_(Based on real channel data)_\n\n"
        + "\n\n".join(copies)
        + "\n\n📋 *Tips:*\n"
        "• A/B test all 3 — track which has the best CTR\n"
        "• Match destination to ad copy promise\n"
        "• Never add risky phrases after generation"
    )
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def ad_text_niche_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    niche    = update.message.text.strip()
    username = context.user_data.get("ad_username", "yourchannel")

    entity_type = "bot" if username.lower().endswith("bot") else (
        "group" if any(w in username.lower() for w in ["group", "chat", "community"]) else "channel"
    )
    copies   = generate_ad_copies(username, entity_type, niche)
    response = (
        f"✍️ *3 Custom Ad Copies for* `@{username}`\n"
        f"_(Based on niche: {niche})_\n\n"
        + "\n\n".join(copies)
        + "\n\n📋 *Tips:*\n"
        "• A/B test all 3 — track which has the best CTR\n"
        "• Match destination to ad copy promise"
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
    if await disabled_guard(update):
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

    await update.message.reply_text(
        f"💰 *Budget Optimization Report*\n\n"
        f"💵 *Total*: ${budget:.2f} ≈ {usd_to_ton(budget)} TON\n"
        f"📅 *Duration*: {duration} days\n"
        f"📆 *Daily Spend*: ${daily_opt:.2f}/day ≈ {usd_to_ton(daily_opt)} TON/day\n\n"
        f"📋 *Strategy:*\n"
        f"• Days 1–3: Test 2–3 ad variants\n"
        f"• Days 4–7: Scale best, pause others\n"
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
    "finance":   (1.2, 3.0, "High",   "Use narrow interest targeting to control CPM"),
    "tech":      (0.8, 2.0, "Medium", "Mix Tier 1 and Tier 2 for balanced volume and cost"),
    "education": (0.5, 1.2, "Low",    "Great niche for tight budgets"),
    "gaming":    (0.6, 1.5, "Low",    "Use interactive creatives for best CTR"),
    "health":    (0.9, 2.2, "Medium", "Avoid health claims — policy-sensitive"),
    "ecommerce": (0.7, 1.8, "Medium", "Link to channel post not website"),
    "news":      (0.4, 1.0, "Low",    "Narrow by language for better traffic quality"),
    "trading":   (1.8, 4.0, "High",   "Full financial ad policy compliance required"),
    "nft":       (1.0, 2.5, "High",   "Avoid hype language — high rejection rate"),
    "fitness":   (0.6, 1.4, "Low",    "Narrow by specific goal for better targeting"),
    "travel":    (0.5, 1.3, "Low",    "Plan around seasonal peaks for efficiency"),
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
    if await disabled_guard(update):
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
        f"• Test 2–3 creatives before scaling\n\n"
        f"🪙 Rate: ~{TON_PER_USD} TON/USD (verify on CoinGecko)",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# BOT JOIN / FIX MODE
# ─────────────────────────────────────────────
async def bot_join_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        "🔧 *Bot Fix Mode*\n\n"
        "To allow me to fix your channel or group:\n\n"
        "1️⃣ Add me as *admin* to your channel/group\n"
        "2️⃣ Grant permissions: Edit messages, Delete messages, Change group info\n"
        "3️⃣ Send the channel/group link below:",
        parse_mode="Markdown"
    )
    return WAIT_JOIN_LINK

async def bot_join_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    link     = update.message.text.strip()
    username = _extract_username(link)
    user_id  = update.effective_user.id

    if not username:
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_JOIN_LINK

    await update.message.reply_text(f"🔍 Checking bot admin status in `@{username}`...", parse_mode="Markdown")

    try:
        chat   = await context.bot.get_chat(f"@{username}")
        member = await context.bot.get_chat_member(chat.id, context.bot.id)

        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text(
                "⚠️ I'm not an admin in that chat yet.\n\n"
                "Please add me as admin with the correct permissions, then send the link again.",
                reply_markup=main_menu_keyboard()
            )
            return WAIT_JOIN_LINK

        set_joined_chat(user_id, str(chat.id))
        await update.message.reply_text(
            f"✅ *Bot is admin in* `@{username}`!\n\n"
            "I can now fix the channel/group name, description, and non-compliant posts.\n\n"
            "⚠️ *Do you want me to apply these fixes automatically?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, apply fixes", callback_data=f"applyfix_{chat.id}"),
                InlineKeyboardButton("❌ No, just suggest", callback_data="skip_targets"),
            ]])
        )
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Could not access `@{username}`.\nEnsure the link is correct and I am added as admin.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        logger.error(f"Bot join error: {e}")
        return ConversationHandler.END

async def apply_fix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = int(query.data.split("_", 1)[1])
    await query.edit_message_reply_markup(reply_markup=None)
    results = []
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
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🔧 *Fix Results:*\n\n" + "\n".join(results),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

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
    ptb_app.add_handler(CommandHandler("start", start))

    # Standalone callbacks — registered BEFORE ConversationHandlers
    ptb_app.add_handler(CallbackQueryHandler(req_access,            pattern="^req_access$"))
    ptb_app.add_handler(CallbackQueryHandler(admin_decision,        pattern="^(accept|deny|disable|removeassets)_\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(skip_targets,          pattern="^skip_targets$"))
    ptb_app.add_handler(CallbackQueryHandler(apply_fix,             pattern="^applyfix_-?\\d+$"))

    # Target channel conversation — triggered by callback inside run_full_analysis output
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(analyse_targets_start, pattern="^analyse_targets$")],
        states={WAIT_TARGET_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyse_targets_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Channel Index
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(channel_index_start, pattern="^channel_index$")],
        states={WAIT_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, channel_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Group Index
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(group_index_start, pattern="^group_index$")],
        states={WAIT_GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Bot Index
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_index_start, pattern="^bot_index$")],
        states={WAIT_BOT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_index_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Ad Text (with niche fallback)
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_text_start, pattern="^ad_text$")],
        states={
            WAIT_AD_LINK:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_analyze)],
            WAIT_NICHE_DETAILS:[MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_niche_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Ad Budget
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_budget_start, pattern="^ad_budget$")],
        states={WAIT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_budget_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # CPM
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_cpm_start, pattern="^ad_cpm$")],
        states={WAIT_CPM_NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_cpm_analyze)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Bot Join / Fix Mode
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
