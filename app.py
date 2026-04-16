"""
AdApprovalPilot AI — Production Build
Deep Telegram Ads Compliance Engine
"""
import os
import logging
import asyncio
import sqlite3
import re
import json
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    # Core users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            access_status TEXT DEFAULT 'pending',
            joined_chat   TEXT DEFAULT NULL
        )
    """)
    # Multi-link approvals table
    c.execute("""
        CREATE TABLE IF NOT EXISTS link_approvals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            link        TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            UNIQUE(user_id, link)
        )
    """)
    # Migrate old schema
    for col, defn in [("joined_chat", "TEXT DEFAULT NULL")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except Exception:
            pass
    # Remove legacy used_link column usage gracefully
    conn.commit()
    conn.close()

# ── User helpers ──
def upsert_user(user_id, username, first_name, status="pending"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, username, first_name, access_status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
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

def get_user_info(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, first_name, access_status FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

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

# ── Multi-link approval helpers ──
def get_link_status(user_id, link):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status FROM link_approvals WHERE user_id=? AND link=?", (user_id, link))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def upsert_link_request(user_id, link, status="pending"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO link_approvals (user_id, link, status)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, link) DO UPDATE SET status=excluded.status
    """, (user_id, link, status))
    conn.commit()
    conn.close()

def set_link_status(user_id, link, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE link_approvals SET status=? WHERE user_id=? AND link=?",
        (status, user_id, link)
    )
    conn.commit()
    conn.close()

def get_approved_links(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT link FROM link_approvals WHERE user_id=? AND status='approved'", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def reset_user_links(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM link_approvals WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# KEYBOARDS
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

def admin_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Persistent admin control panel for a specific user."""
    uid = str(user_id)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve",        callback_data=f"accept_{uid}"),
            InlineKeyboardButton("❌ Deny",           callback_data=f"deny_{uid}"),
        ],
        [
            InlineKeyboardButton("🚫 Disable",        callback_data=f"disable_{uid}"),
            InlineKeyboardButton("🔁 Reset Access",   callback_data=f"reset_{uid}"),
        ],
        [InlineKeyboardButton("🗑 Remove From Channels", callback_data=f"removeassets_{uid}")],
    ])

def admin_link_keyboard(user_id: int, link: str) -> InlineKeyboardMarkup:
    """Keyboard for approving/denying a specific link request."""
    safe_link = link.replace("https://t.me/", "").replace("/", "")[:50]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve Link", callback_data=f"approvelink_{user_id}_{safe_link}"),
        InlineKeyboardButton("❌ Deny Link",    callback_data=f"denylink_{user_id}_{safe_link}"),
    ]])

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# COMPLIANCE DETECTION ENGINE
# ─────────────────────────────────────────────

# Category-based violation detection
VIOLATION_CATEGORIES = {
    "gambling": [
        "casino", "gambling", "bet ", "betting", "jackpot", "poker",
        "roulette", "slots", "bookie", "odds", "wager", "stake",
    ],
    "adult": [
        "xxx", "adult content", "18+", "nsfw", "explicit", "nude",
        "onlyfans", "escort", "dating",
    ],
    "get_rich_quick": [
        "earn fast", "get rich", "make money fast", "instant profit",
        "easy money", "fast cash", "make $", "earn $", "passive income",
        "financial freedom", "quit your job", "no experience needed",
    ],
    "financial_promises": [
        "guaranteed returns", "guaranteed profit", "100% profit",
        "guaranteed income", "risk free investment", "no risk",
        "double your money", "triple your investment", "100x",
        "guaranteed roi", "fixed returns",
    ],
    "crypto_hype": [
        "moon", "lambo", "to the moon", "next bitcoin", "100x coin",
        "pump", "get in early", "presale", "airdrop bonus",
        "free crypto", "crypto signal", "forex signal", "vip signal",
        "signal group", "next 100x",
    ],
    "scam_signals": [
        "ponzi", "mlm", "referral bonus", "recruit members",
        "join my team", "unlimited earning", "work from home earn",
        "secret method", "hack the market", "insider tip",
    ],
    "affiliate_abuse": [
        "click my link", "use my code", "referral link",
        "affiliate", "commission", "earn per click",
    ],
    "spam_structure": [
        "join now!!!",  "limited time offer!!", "act now!!",
        "don't miss out!!", "last chance!!",
    ],
}

SUSPICIOUS_LINKS = [
    r"bit\.ly", r"tinyurl", r"shorte\.st", r"cutt\.ly",
    r"gg\.gg", r"t\.cn", r"rebrand\.ly", r"is\.gd", r"ow\.ly",
]

REWRITE_MAP = {
    "earn fast":           "grow your expertise quickly",
    "make money":          "build financial value",
    "get rich":            "achieve your goals",
    "guaranteed":          "proven",
    "guarantee":           "trusted",
    "100%":                "highly effective",
    "no risk":             "beginner-friendly",
    "risk free":           "accessible",
    "free money":          "free resources",
    "instant profit":      "measurable results",
    "passive income":      "consistent returns",
    "work from home":      "remote opportunities",
    "double your":         "grow your",
    "click now":           "learn more",
    "act now":             "get started",
    "limited time":        "exclusive",
    "winner":              "top performer",
    "prize":               "reward",
    "join now":            "join us",
    "don't miss":          "explore",
    "airdrop":             "token distribution",
    "get paid":            "earn value",
    "fast cash":           "quick results",
    "easy money":          "accessible opportunity",
    "moon":                "growth potential",
    "pump":                "market movement",
    "signal":              "market insight",
    "crypto signal":       "market analysis",
    "forex signal":        "currency analysis",
    "passive income":      "recurring value",
    "financial freedom":   "financial independence",
}


def detect_violations(text: str) -> dict:
    """
    Scan text for policy violations by category.
    Returns dict of {category: [found_phrases]}
    """
    if not text:
        return {}
    t       = text.lower()
    results = {}
    for category, phrases in VIOLATION_CATEGORIES.items():
        found = [p for p in phrases if p in t]
        if found:
            results[category] = found
    # Suspicious links
    found_links = [p for p in SUSPICIOUS_LINKS if re.search(p, t)]
    if found_links:
        results["suspicious_links"] = found_links
    # Excessive caps
    caps_words = [w for w in text.split() if len(w) > 3 and w.isupper()]
    if len(caps_words) >= 3:
        results["excessive_caps"] = caps_words[:5]
    return results


def violation_explanation(category: str, phrases: list) -> str:
    """Human-readable explanation for each violation category."""
    explanations = {
        "gambling": (
            "Contains gambling/betting content. Telegram Ads strictly prohibits "
            f"gambling promotions. Detected: `{'`, `'.join(phrases)}`"
        ),
        "adult": (
            "Contains adult or sensitive content indicators. "
            f"Detected: `{'`, `'.join(phrases)}`"
        ),
        "get_rich_quick": (
            "Uses 'get rich quick' language which Telegram's review system "
            f"flags as misleading. Detected: `{'`, `'.join(phrases)}`"
        ),
        "financial_promises": (
            "Contains financial guarantees or unrealistic return promises. "
            "This is a direct policy violation. "
            f"Detected: `{'`, `'.join(phrases)}`"
        ),
        "crypto_hype": (
            "Uses crypto hype language that triggers automatic policy flags. "
            f"Detected: `{'`, `'.join(phrases)}`"
        ),
        "scam_signals": (
            "Contains patterns associated with scam or MLM operations. "
            f"Detected: `{'`, `'.join(phrases)}`"
        ),
        "affiliate_abuse": (
            "Excessive affiliate or referral link promotion detected. "
            "Telegram limits direct affiliate solicitation in ads. "
            f"Detected: `{'`, `'.join(phrases)}`"
        ),
        "spam_structure": (
            "Post structure resembles spam (excessive punctuation, urgency manipulation). "
            f"Detected: `{'`, `'.join(phrases)}`"
        ),
        "suspicious_links": (
            "Contains shortened or suspicious URLs which Telegram flags as spam vectors. "
            f"Patterns: `{'`, `'.join(phrases)}`"
        ),
        "excessive_caps": (
            "Excessive ALL-CAPS words signal low-quality promotional content. "
            f"Words: `{'`, `'.join(phrases)}`"
        ),
    }
    return explanations.get(category, f"Policy violation in category `{category}`")


def smart_recommendation(category: str) -> str:
    """Generate targeted recommendation per violation type."""
    recs = {
        "gambling":           "Remove all gambling/betting content before running ads. Telegram does not allow gambling promotion.",
        "adult":              "Remove adult content entirely. This is a hard policy block.",
        "get_rich_quick":     "Replace motivational income language with specific, factual value statements.",
        "financial_promises": "Remove all guaranteed returns or profit claims. Use 'potential' or 'possible' instead.",
        "crypto_hype":        "Replace hype language with analytical, factual descriptions of your crypto content.",
        "scam_signals":       "Restructure content to focus on education and value, not recruitment or referrals.",
        "affiliate_abuse":    "Limit affiliate links to 1 per post. Add value content between promotions.",
        "spam_structure":     "Remove excessive punctuation and urgency language. Use calm, professional tone.",
        "suspicious_links":   "Replace shortened URLs with full, transparent links to build trust.",
        "excessive_caps":     "Use sentence case throughout. Reserve caps for brand names only.",
    }
    return recs.get(category, "Review and update content to align with Telegram Ads policies.")


def rewrite_text(text: str) -> str:
    """Rewrite post text to be policy-compliant."""
    cleaned = text
    for phrase, safe in REWRITE_MAP.items():
        cleaned = re.sub(re.escape(phrase), safe, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'!{2,}', '.', cleaned)
    cleaned = re.sub(r'\?{2,}', '?', cleaned)
    def fix_caps(m):
        w = m.group(0)
        return w.capitalize() if len(w) > 3 else w
    cleaned = re.sub(r'\b[A-Z]{4,}\b', fix_caps, cleaned)
    return cleaned.strip()


def analyze_profile_username(username: str, entity_type: str) -> dict:
    """Analyze username patterns for profile-level issues."""
    issues = []
    score  = 100

    if len(username) < 5:
        issues.append(("username_length", "Username too short (<5 chars) — reduces trust score", 20))
    if username.isupper():
        issues.append(("username_caps", "All-caps username appears spammy to reviewers", 15))
    if "__" in username:
        issues.append(("double_underscore", "Double underscores signal low-quality account", 10))
    if re.search(r'\d{3,}$', username):
        issues.append(("trailing_numbers", "Trailing numbers suggest auto-generated or spam account", 10))

    for kw in ["free", "earn", "money", "profit", "win", "casino", "bet", "signal", "forex", "pump"]:
        if kw in username.lower():
            issues.append(("risky_keyword", f"`{kw}` in username is a direct Telegram Ads policy risk", 30))
            break

    if entity_type == "bot" and not username.lower().endswith("bot"):
        issues.append(("bot_naming", "Bot username should end with 'bot' per Telegram convention", 10))

    for _, _, penalty in issues:
        score -= penalty
    return {"issues": issues, "score": max(0, score)}


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
    if entity_type == "channel":
        return [
            f"📢 *Copy 1 — Informational*\nStay informed with *{b}* — expert insights trusted by an engaged audience. ➡️ Explore now.",
            f"📢 *Copy 2 — Community*\nReliable, high-quality content in your niche. *{b}* delivers consistently. ➡️ Subscribe.",
            f"📢 *Copy 3 — Value*\n*{b}* shares practical knowledge with no fluff. Level up your expertise. ➡️ Follow.",
        ]
    elif entity_type == "group":
        return [
            f"📢 *Copy 1 — Community*\nJoin *{b}* — where members share insights and grow together. ➡️ Join now.",
            f"📢 *Copy 2 — Engagement*\nReal discussions. Expert opinions. *{b}* is built for serious learners. ➡️ Join today.",
            f"📢 *Copy 3 — Trust*\n*{b}* is a moderated, professional space for your niche. ➡️ Connect.",
        ]
    else:
        return [
            f"📢 *Copy 1 — Utility*\nAutomate and simplify with *{b}*. Smart tools inside Telegram. ➡️ Start now.",
            f"📢 *Copy 2 — Efficiency*\nSave time with *{b}*. Built for real users who want results. ➡️ Try it.",
            f"📢 *Copy 3 — Trust*\nThousands use *{b}* daily. Reliable and easy to use. ➡️ Get started.",
        ]

# ─────────────────────────────────────────────
# REAL TELEGRAM DATA FETCHER
# ─────────────────────────────────────────────
async def fetch_chat_data(bot, username: str) -> dict:
    """Fetch ONLY real data from Telegram API. Never generates fake data."""
    result = {
        "success":         False,
        "error":           None,
        "name":            None,
        "description":     None,
        "username":        username,
        "member_count":    None,
        "chat_type":       None,
        "has_description": False,
        "has_photo":       False,
    }
    try:
        chat = await bot.get_chat(f"@{username}")
        result.update({
            "success":         True,
            "name":            chat.title or chat.full_name or username,
            "description":     chat.description or chat.bio or None,
            "has_description": bool(chat.description or chat.bio),
            "has_photo":       bool(chat.photo),
            "chat_type":       chat.type,
        })
        try:
            result["member_count"] = await bot.get_chat_member_count(f"@{username}")
        except Exception:
            pass
    except Forbidden:
        result["error"] = "private_or_restricted"
    except BadRequest as e:
        result["error"] = f"bad_request: {e}"
    except TelegramError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    return result

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
        await query.edit_message_text("🚫 *Access Suspended.*\n\nContact @BlockSavvyMx to appeal.", parse_mode="Markdown")
        return False
    if status != "approved":
        await query.answer("🔒 Request access first!", show_alert=True)
        await query.edit_message_text(
            "🔒 *Access Required*\n\nClick *🔑 Request Admin Access* to get started.",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return False
    return True

async def disabled_guard(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and get_user_status(user_id) == "disabled":
        await update.message.reply_text("🚫 Access suspended. Contact admin @BlockSavvyMx.")
        return True
    return False

async def link_access_check(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str) -> bool:
    """
    Multi-link approval:
    - Admin: always allowed
    - Approved link: allowed
    - New link: request admin approval
    """
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True

    link_status = get_link_status(user_id, link)

    if link_status == "approved":
        return True

    if link_status == "pending":
        await update.message.reply_text(
            "⏳ *Approval Pending*\n\n"
            f"Your request to analyse `{link}` is still awaiting admin approval.\n"
            "Please wait for @BlockSavvyMx to approve it.",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return False

    if link_status == "denied":
        await update.message.reply_text(
            "❌ *Link Access Denied*\n\n"
            f"Admin has denied analysis of `{link}`.\n"
            "Contact @BlockSavvyMx if you believe this is a mistake.",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return False

    # New link — request admin approval
    upsert_link_request(user_id, link, "pending")
    user_info = get_user_info(user_id)
    uname     = user_info[0] if user_info else "N/A"
    fname     = user_info[1] if user_info else "N/A"

    # Store link in context for callback resolution
    context.bot_data[f"link_req_{user_id}_{link[:50]}"] = link

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔗 *New Link Analysis Request*\n\n"
                f"👤 Name: {fname}\n"
                f"🆔 User ID: `{user_id}`\n"
                f"📛 Username: @{uname}\n"
                f"🔗 Link: `{link}`"
            ),
            parse_mode="Markdown",
            reply_markup=admin_link_keyboard(user_id, link)
        )
    except Exception as e:
        logger.error(f"Admin link notify failed: {e}")

    await update.message.reply_text(
        "📨 *Link Approval Requested*\n\n"
        f"Your request to analyse `{link}` has been sent to the admin.\n"
        "You'll be notified once approved.",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return False

# ─────────────────────────────────────────────
# DEEP ANALYSIS ENGINE
# ─────────────────────────────────────────────
async def run_deep_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: str,
    entity_type: str
):
    """
    Full deep analysis using ONLY real Telegram API data.
    Builds a root-cause diagnosis report.
    """
    username = _extract_username(link)
    user_id  = update.effective_user.id

    await update.message.reply_text(
        f"🔍 *Running deep compliance analysis on* `@{username}`...\n"
        "Fetching real data from Telegram API.",
        parse_mode="Markdown"
    )

    chat_data = await fetch_chat_data(context.bot, username)

    if not chat_data["success"]:
        err = chat_data["error"] or ""
        if "private_or_restricted" in err:
            await update.message.reply_text(
                "🔒 *Private or Restricted Channel*\n\n"
                "Cannot access this channel. It may be private or restricted.\n\n"
                "Options:\n"
                "• Make it public temporarily, OR\n"
                "• Use *🔧 Allow Bot to Fix* to add me as admin for full access.",
                parse_mode="Markdown", reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "⚠️ *Unable to Access Data*\n\n"
                "Could not fetch data for this channel/group.\n"
                "Please verify the link is correct and the channel is public.",
                parse_mode="Markdown", reply_markup=main_menu_keyboard()
            )
        return

    # ── Collect all detected issues ──
    root_causes   = []
    all_recs      = []
    total_penalty = 0

    # 1. Trust & authority
    trust_issues = []
    member_count = chat_data["member_count"]
    if member_count is not None:
        if member_count < 500:
            trust_issues.append(f"Very low subscriber base ({member_count:,} users) — extremely low trust signal")
            total_penalty += 40
        elif member_count < 1000:
            trust_issues.append(f"Low subscriber base ({member_count:,} users) — below Telegram Ads minimum trust threshold")
            total_penalty += 25
        elif member_count < 5000:
            trust_issues.append(f"Moderate subscriber base ({member_count:,} users) — may reduce ad confidence")
            total_penalty += 10
    else:
        trust_issues.append("Subscriber count unavailable — cannot verify audience size")
        total_penalty += 15

    if trust_issues:
        root_causes.append(("🔴 Trust & Authority Issue", trust_issues))
        for _ in trust_issues:
            if member_count is not None and member_count < 1000:
                all_recs.append("Grow your channel to at least 1,000–5,000+ subscribers before running ads")

    # 2. Profile quality
    profile       = analyze_profile_username(username, entity_type)
    profile_issues = []

    if not chat_data["has_description"]:
        profile_issues.append("No description set — empty description is a known ad rejection trigger")
        total_penalty += 20
        all_recs.append("Add a clear, niche-specific description to your channel/group")
    else:
        desc_violations = detect_violations(chat_data["description"] or "")
        if desc_violations:
            for cat, phrases in desc_violations.items():
                profile_issues.append(violation_explanation(cat, phrases))
                all_recs.append(smart_recommendation(cat))
                total_penalty += 20

    if not chat_data["has_photo"]:
        profile_issues.append("No profile photo — reduces brand trust signal")
        total_penalty += 10
        all_recs.append("Add a professional profile photo to increase trust score")

    for issue_tuple in profile["issues"]:
        profile_issues.append(issue_tuple[1])
        total_penalty += issue_tuple[2]
        all_recs.append(f"Fix username: {issue_tuple[1].split('—')[0].strip()}")

    if profile_issues:
        root_causes.append(("🟡 Profile Quality Issues", profile_issues))

    # 3. Content analysis (description as proxy — posts require admin access)
    content_issues = []
    if chat_data["description"]:
        desc_v = detect_violations(chat_data["description"])
        if desc_v:
            for cat, phrases in desc_v.items():
                content_issues.append(violation_explanation(cat, phrases))
                total_penalty += 15

    if content_issues:
        root_causes.append(("🔴 Content Policy Violations", content_issues))

    # ── Calculate overall risk ──
    if total_penalty >= 60:
        risk_level  = "🔴 HIGH RISK — Ad approval very unlikely"
    elif total_penalty >= 30:
        risk_level  = "🟡 MEDIUM RISK — Ad approval uncertain"
    else:
        risk_level  = "🟢 LOW RISK — Good approval chances"

    # ── Build root-cause diagnosis ──
    emoji  = {"channel": "📊", "group": "👥", "bot": "🤖"}.get(entity_type, "🔍")
    report = (
        f"{emoji} *Deep Compliance Report*\n"
        f"🔗 `{link}`  |  `@{username}`\n"
        f"📛 {chat_data['name']}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Overall Risk*: {risk_level}\n"
        f"📉 *Risk Score*: {min(total_penalty, 100)}/100\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if member_count is not None:
        report += f"👥 *Subscribers*: {member_count:,}\n"
        if member_count < 1000:
            report += (
                "⚠️ *Low Trust Level Detected*\n"
                f"Channels with fewer than 1,000 subscribers face low approval confidence.\n"
                "➡️ Grow to 1,000–5,000+ before running ads.\n\n"
            )
        else:
            report += "\n"
    else:
        report += "👥 *Subscribers*: Could not fetch\n\n"

    # Root cause section
    if root_causes:
        report += "🩺 *Root Cause Diagnosis*\n"
        report += "_Why your ads are likely being declined:_\n\n"
        for i, (title, issues) in enumerate(root_causes, 1):
            report += f"*{i}. {title}:*\n"
            for issue in issues:
                report += f"   • {issue}\n"
            report += "\n"
    else:
        report += "✅ *No major compliance issues detected.*\n\n"

    # Name alternatives
    name_alts = generate_name_alternatives(username, entity_type)
    report += "✏️ *Name Alternatives:*\n" + "\n".join(f"  • {a}" for a in name_alts) + "\n\n"

    # Deduplicated recommendations
    if all_recs:
        unique_recs = list(dict.fromkeys(all_recs))
        report += "📋 *Expert Recommendations:*\n"
        for rec in unique_recs[:6]:
            report += f"  ➡️ {rec}\n"
        report += "\n"

    # Post scan notice
    report += (
        "📋 *Post-Level Scan*:\n"
        "Add me as admin via *🔧 Allow Bot to Fix My Channel/Group* "
        "to enable full post scanning and auto-fix.\n\n"
    )

    # Summary conclusion
    if total_penalty >= 60:
        report += (
            "⚠️ *Summary*: These combined signals significantly reduce Telegram Ads "
            "approval confidence. Address all issues above before submitting ads."
        )
    elif total_penalty >= 30:
        report += (
            "⚠️ *Summary*: Several factors are reducing your approval chances. "
            "Fixing the issues above will improve your ad acceptance rate."
        )
    else:
        report += "✅ *Summary*: Your channel shows good compliance signals. Minor improvements recommended."

    # Store for target channel flow
    context.user_data.update({
        "main_link":        link,
        "main_entity_type": entity_type,
        "main_description": chat_data.get("description", ""),
    })

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📡 Analyse Target Channels", callback_data="analyse_targets"),
        InlineKeyboardButton("⏭ Skip",                    callback_data="skip_targets"),
    ]])

    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=keyboard)


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
        "🚀 Request access below to get started.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

# ─────────────────────────────────────────────
# ACCESS REQUEST — ALWAYS NOTIFIES ADMIN
# ─────────────────────────────────────────────
async def req_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user

    if user.id == ADMIN_ID:
        await query.edit_message_text("👑 You are the admin — full access granted!", reply_markup=main_menu_keyboard())
        return

    status = get_user_status(user.id)
    if status == "disabled":
        await query.edit_message_text("🚫 Access suspended. Contact @BlockSavvyMx.", reply_markup=main_menu_keyboard())
        return

    # Always notify admin regardless of current status
    # This allows re-requests and admin to see panel at any time
    upsert_user(user.id, user.username, user.first_name,
                status if status in ("approved", "disabled") else "pending")

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 *Access Request*\n\n"
                f"👤 Name: {user.first_name}\n"
                f"🆔 User ID: `{user.id}`\n"
                f"📛 Username: @{user.username or 'N/A'}\n"
                f"📊 Current Status: `{status or 'new'}`"
            ),
            parse_mode="Markdown",
            reply_markup=admin_user_keyboard(user.id)
        )
        if status == "approved":
            msg = "✅ You already have access! Your request has been re-sent to admin for review."
        else:
            msg = "⏳ *Request sent!*\n\nWait for admin approval. You'll be notified."
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Admin notify failed: {e}")
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

    parts     = query.data.split("_", 1)
    action    = parts[0]
    target_id = int(parts[1])

    if action == "accept":
        set_user_status(target_id, "approved")
        # Re-send persistent admin panel
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ User `{target_id}` *approved*.\n\n_Admin panel remains active below:_",
            parse_mode="Markdown",
            reply_markup=admin_user_keyboard(target_id)
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "✅ *Access Granted!*\n\n"
                "You now have full access to AdApprovalPilot AI.\n"
                "Use /start to open the menu.\n\n"
                "📌 Each new link you analyse requires separate admin approval."
            ),
            parse_mode="Markdown"
        )

    elif action == "deny":
        set_user_status(target_id, "denied")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ User `{target_id}` *denied*.\n\n_Admin panel:_",
            parse_mode="Markdown",
            reply_markup=admin_user_keyboard(target_id)
        )
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ *Access Denied.*\n\nContact @BlockSavvyMx if this is a mistake.",
            parse_mode="Markdown"
        )

    elif action == "disable":
        set_user_status(target_id, "disabled")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚫 User `{target_id}` *disabled*.\n\n_Admin panel:_",
            parse_mode="Markdown",
            reply_markup=admin_user_keyboard(target_id)
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🚫 *Access suspended by admin.*\n\nContact @BlockSavvyMx to appeal.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "reset":
        set_user_status(target_id, "pending")
        reset_user_links(target_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔁 User `{target_id}` access *reset*. All approved links cleared.\n\n_Admin panel:_",
            parse_mode="Markdown",
            reply_markup=admin_user_keyboard(target_id)
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🔁 *Your access has been reset.*\n\nPlease request access again via /start.",
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
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🗑 Bot left chat `{joined}` for user `{target_id}`.\n\n_Admin panel:_",
                    parse_mode="Markdown",
                    reply_markup=admin_user_keyboard(target_id)
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ Could not leave chat `{joined}`: {e}",
                    parse_mode="Markdown",
                    reply_markup=admin_user_keyboard(target_id)
                )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"ℹ️ No active chat for user `{target_id}`.\n\n_Admin panel:_",
                parse_mode="Markdown",
                reply_markup=admin_user_keyboard(target_id)
            )

# ─────────────────────────────────────────────
# LINK APPROVAL CALLBACKS
# ─────────────────────────────────────────────
async def link_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return

    # Parse: approvelink_<user_id>_<safe_link> or denylink_<user_id>_<safe_link>
    parts      = query.data.split("_", 2)
    action     = parts[0]      # approvelink / denylink
    target_id  = int(parts[1])
    safe_link  = parts[2]

    # Recover full link from bot_data
    full_link = context.bot_data.get(f"link_req_{target_id}_{safe_link}", f"https://t.me/{safe_link}")

    if action == "approvelink":
        set_link_status(target_id, full_link, "approved")
        await query.edit_message_text(
            f"✅ Link `{full_link}` approved for user `{target_id}`.",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"✅ *Link Approved!*\n\n"
                f"You can now analyse:\n`{full_link}`\n\n"
                "Use the Channel/Group/Bot Index button to proceed."
            ),
            parse_mode="Markdown"
        )
    else:
        set_link_status(target_id, full_link, "denied")
        await query.edit_message_text(
            f"❌ Link `{full_link}` denied for user `{target_id}`.",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=f"❌ *Link Denied*\n\nAdmin denied analysis of:\n`{full_link}`\n\nContact @BlockSavvyMx for more info.",
            parse_mode="Markdown"
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
            "Send the list of target channels/groups used in your ad campaign.\n\n"
            "One per line:\n"
            "`https://t.me/channel1`\n"
            "`https://t.me/channel2`\n\n"
            "Or /cancel to return to menu."
        ),
        parse_mode="Markdown"
    )
    return WAIT_TARGET_LINKS

async def analyse_targets_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    lines = [l.strip() for l in update.message.text.strip().split("\n") if l.strip()]
    if not lines:
        await update.message.reply_text("⚠️ No links found. Send at least one link.")
        return WAIT_TARGET_LINKS

    await update.message.reply_text(f"🔍 Analysing {len(lines)} target(s) using real Telegram data...")

    report = "📡 *Target Channel Risk Report*\n_(Based on real Telegram data only)_\n\n"

    for link in lines:
        username = _extract_username(link)
        if not username:
            report += f"⚠️ Invalid: `{link}` — skipped\n\n━━━━━━━━━━━━━━━━━━\n\n"
            continue

        chat_data = await fetch_chat_data(context.bot, username)

        if not chat_data["success"]:
            report += (
                f"🎯 *Target*: `@{username}`\n"
                "⚠️ Unable to access — private or restricted.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
            )
            continue

        risk_score  = 0
        risk_flags  = []
        suggestions = []

        count = chat_data["member_count"]
        if count is not None:
            if count < 500:
                risk_score += 50
                risk_flags.append(f"Very low audience ({count:,} subscribers — high rejection risk)")
                suggestions.append("Grow to 1,000+ before using as ad target")
            elif count < 1000:
                risk_score += 30
                risk_flags.append(f"Low subscriber count ({count:,})")
                suggestions.append("Aim for 5,000+ subscribers for stronger placement")
            elif count < 5000:
                risk_score += 10
                risk_flags.append(f"Moderate subscriber count ({count:,})")
        else:
            risk_score += 20
            risk_flags.append("Subscriber count unavailable")

        if not chat_data["has_description"]:
            risk_score += 25
            risk_flags.append("No description — weak profile signal")
            suggestions.append("Add a niche-specific description")
        else:
            desc_v = detect_violations(chat_data["description"] or "")
            for cat, phrases in desc_v.items():
                risk_score += 20
                risk_flags.append(violation_explanation(cat, phrases))
                suggestions.append(smart_recommendation(cat))

        if not chat_data["has_photo"]:
            risk_score += 10
            risk_flags.append("No profile photo")
            suggestions.append("Add a professional profile photo")

        risk_label = (
            "🔴 HIGH RISK" if risk_score >= 50 else
            "🟡 MEDIUM RISK" if risk_score >= 25 else
            "🟢 LOW RISK"
        )

        report += f"🎯 *Target*: `@{username}`\n"
        report += f"📛 {chat_data['name']}\n"
        if count is not None:
            report += f"👥 {count:,} subscribers\n"
        report += f"⚠️ *Risk Level*: {risk_label}\n\n"
        if risk_flags:
            report += "*Reasons (real data only):*\n" + "\n".join(f"  • {f}" for f in risk_flags) + "\n\n"
        if suggestions:
            report += "*Recommendations:*\n" + "\n".join(f"  ➡️ {s}" for s in suggestions) + "\n\n"
        report += "━━━━━━━━━━━━━━━━━━\n\n"
        await asyncio.sleep(0.5)

    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def skip_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="✅ Analysis complete. Use /start to return to main menu.",
        reply_markup=main_menu_keyboard()
    )

# ─────────────────────────────────────────────
# CHANNEL / GROUP / BOT INDEX
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
    if not await link_access_check(update, context, link):
        return ConversationHandler.END
    await run_deep_analysis(update, context, link, "channel")
    return ConversationHandler.END

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
    if not await link_access_check(update, context, link):
        return ConversationHandler.END
    await run_deep_analysis(update, context, link, "group")
    return ConversationHandler.END

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
    link     = update.message.text.strip()
    username = _extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link.", parse_mode="Markdown")
        return WAIT_BOT_LINK
    if not await link_access_check(update, context, link):
        return ConversationHandler.END

    await update.message.reply_text("🔍 Fetching real bot data from Telegram...")
    chat_data = await fetch_chat_data(context.bot, username)
    profile   = analyze_profile_username(username, "bot")
    score     = profile["score"]
    score_lbl = "🟢 Good" if score >= 80 else ("🟡 Needs Improvement" if score >= 50 else "🔴 High Risk")
    name_alts = generate_name_alternatives(username, "bot")

    report = (
        f"🤖 *Bot Compliance Report*\n"
        f"🔗 `{link}`  |  `@{username}`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Profile Score*: {score}/100 — {score_lbl}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )
    if chat_data["success"]:
        report += f"📛 Name: *{chat_data['name']}*\n"
        if chat_data["has_description"]:
            desc   = chat_data["description"] or ""
            desc_v = detect_violations(desc)
            report += f"📝 Description: _{desc[:200]}_\n"
            if desc_v:
                for cat, phrases in desc_v.items():
                    report += f"  ❌ {violation_explanation(cat, phrases)}\n"
            else:
                report += "  ✅ Description is clean.\n"
        else:
            report += "📝 Description: Not set ⚠️\n"
        report += f"🖼 Photo: {'✅ Set' if chat_data['has_photo'] else '❌ Not set'}\n\n"
    else:
        report += "⚠️ Could not fetch full bot profile data.\n\n"

    for issue_tuple in profile["issues"]:
        report += f"  ❌ {issue_tuple[1]}\n"
    report += "\n"
    report += "✏️ *Name Alternatives:*\n" + "\n".join(f"  • {a}" for a in name_alts) + "\n\n"

    risky_ctas = {"earn": "Get Started", "free": "Explore", "money": "Learn More", "win": "Join", "signal": "Insights"}
    found = [(r, s) for r, s in risky_ctas.items() if r in username.lower()]
    if found:
        report += "🔘 *Risky CTA Patterns in Username:*\n"
        for r, s in found:
            report += f"  ❌ `{r}` → Suggest: `{s}`\n"
        report += "\n"

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
        "Send your channel/group/bot link.\n"
        "I'll generate 3 compliant ad copies based on real channel data.\n\n"
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
        await update.message.reply_text("⚠️ Invalid link.", parse_mode="Markdown")
        return WAIT_AD_LINK

    await update.message.reply_text("✍️ Fetching real channel data for ad copy generation...")
    chat_data   = await fetch_chat_data(context.bot, username)
    description = chat_data.get("description") if chat_data["success"] else None

    if not description:
        await update.message.reply_text(
            "ℹ️ *Could not fetch channel description.*\n\n"
            "Please describe your channel niche so I can generate accurate ad copies.\n\n"
            "Example: 'Crypto trading analysis for beginners in Nigeria'",
            parse_mode="Markdown"
        )
        context.user_data["ad_username"] = username
        return WAIT_NICHE_DETAILS

    entity_type = (
        "bot"     if username.lower().endswith("bot") else
        "group"   if any(w in username.lower() for w in ["group", "chat", "community"]) else
        "channel"
    )
    copies   = generate_ad_copies(username, entity_type, description)
    response = (
        f"✍️ *3 Custom Ad Copies for* `@{username}`\n"
        f"_(Based on real channel data)_\n\n"
        + "\n\n".join(copies)
        + "\n\n📋 *Tips:*\n"
        "• A/B test all 3 — track CTR per copy\n"
        "• Match ad destination to copy promise\n"
        "• Never add risky phrases after generation"
    )
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def ad_text_niche_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    niche    = update.message.text.strip()
    username = context.user_data.get("ad_username", "yourchannel")
    entity_type = (
        "bot"     if username.lower().endswith("bot") else
        "group"   if any(w in username.lower() for w in ["group", "chat", "community"]) else
        "channel"
    )
    copies   = generate_ad_copies(username, entity_type, niche)
    response = (
        f"✍️ *3 Custom Ad Copies for* `@{username}`\n"
        f"_(Based on niche: {niche})_\n\n"
        + "\n\n".join(copies)
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
        f"• Days 1–3: Test 2–3 ad variants simultaneously\n"
        f"• Days 4–7: Scale best performer, pause others\n"
        f"• Pause any ad with CTR below 1% after day 3\n\n"
        f"💡 *Tips:*\n"
        f"• Start in Tier 2 geos (NG, IN, BR) for lower CPM\n"
        f"• Use a channel post as ad destination\n"
        f"• Set frequency cap: 2 impressions/user/day\n\n"
        f"🪙 Rate: ~{TON_PER_USD} TON/USD (verify on CoinGecko)",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# CPM PREDICTOR
# ─────────────────────────────────────────────
CPM_TABLE = {
    "crypto":    (1.5, 3.5, "High",   "Test Tier 2 countries (IN, NG, BR) to reduce CPM"),
    "finance":   (1.2, 3.0, "High",   "Use narrow interest targeting to control costs"),
    "tech":      (0.8, 2.0, "Medium", "Mix Tier 1 and Tier 2 for balanced volume and cost"),
    "education": (0.5, 1.2, "Low",    "Great niche for tight budgets — high engagement rate"),
    "gaming":    (0.6, 1.5, "Low",    "Interactive creatives perform best here"),
    "health":    (0.9, 2.2, "Medium", "Avoid health claims — policy-sensitive niche"),
    "ecommerce": (0.7, 1.8, "Medium", "Link to channel post not website for better quality score"),
    "news":      (0.4, 1.0, "Low",    "Narrow by language for better traffic quality"),
    "trading":   (1.8, 4.0, "High",   "Full financial ad policy compliance required"),
    "nft":       (1.0, 2.5, "High",   "Avoid hype language — very high rejection rate"),
    "fitness":   (0.6, 1.4, "Low",    "Narrow by specific goal for better targeting"),
    "travel":    (0.5, 1.3, "Low",    "Plan campaigns around seasonal peaks"),
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
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
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
        "2️⃣ Grant: Edit messages, Delete messages, Change group info\n"
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
        await update.message.reply_text("⚠️ Invalid link.", parse_mode="Markdown")
        return WAIT_JOIN_LINK

    await update.message.reply_text(f"🔍 Verifying admin status in `@{username}`...", parse_mode="Markdown")

    try:
        chat   = await context.bot.get_chat(f"@{username}")
        member = await context.bot.get_chat_member(chat.id, context.bot.id)

        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text(
                "⚠️ I'm not an admin in that chat yet.\n\n"
                "Add me as admin with the required permissions, then send the link again.",
                reply_markup=main_menu_keyboard()
            )
            return WAIT_JOIN_LINK

        set_joined_chat(user_id, str(chat.id))

        # Notify admin that bot was added
        user_info = get_user_info(user_id)
        uname     = user_info[0] if user_info else "N/A"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 *Bot Added to Channel/Group*\n\n"
                f"👤 User: @{uname} (`{user_id}`)\n"
                f"📢 Chat: `@{username}`\n"
                f"🆔 Chat ID: `{chat.id}`"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Allow Bot to Stay",    callback_data=f"botstay_{chat.id}"),
                InlineKeyboardButton("❌ Remove Bot Now",       callback_data=f"botleave_{chat.id}"),
            ]])
        )

        await update.message.reply_text(
            f"✅ *Bot is admin in* `@{username}`!\n\n"
            "Admin has been notified.\n\n"
            "⚠️ *Do you want me to apply compliance fixes automatically?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, apply fixes", callback_data=f"applyfix_{chat.id}"),
                InlineKeyboardButton("❌ No, just suggest", callback_data="skip_targets"),
            ]])
        )
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Could not verify admin status for `@{username}`.\n"
            "Check the link and ensure I am added as admin.",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        logger.error(f"Bot join error: {e}")
        return ConversationHandler.END

async def bot_stay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return
    await query.edit_message_text("✅ Bot is allowed to stay in the channel/group.", parse_mode="Markdown")

async def bot_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return
    chat_id = int(query.data.split("_", 1)[1])
    try:
        await context.bot.leave_chat(chat_id=chat_id)
        await query.edit_message_text(f"✅ Bot has left chat `{chat_id}`.", parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"⚠️ Could not leave chat: {e}", parse_mode="Markdown")

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
                "Official channel delivering expert insights and curated content. "
                "Follow for reliable, niche-specific updates."
            )
        )
        results.append("✅ Description updated to policy-compliant version")
    except Exception as e:
        results.append(f"⚠️ Description update failed: {e}")
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🔧 *Fix Results:*\n\n" + "\n".join(results) + (
            "\n\n📋 For full post-level scanning and editing, "
            "use Channel/Group Index while I remain as admin."
        ),
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
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
    ptb_app.add_handler(CallbackQueryHandler(req_access,      pattern="^req_access$"))
    ptb_app.add_handler(CallbackQueryHandler(admin_decision,  pattern="^(accept|deny|disable|reset|removeassets)_\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(link_decision,   pattern="^(approvelink|denylink)_\\d+_.+$"))
    ptb_app.add_handler(CallbackQueryHandler(skip_targets,    pattern="^skip_targets$"))
    ptb_app.add_handler(CallbackQueryHandler(apply_fix,       pattern="^applyfix_-?\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(bot_stay,        pattern="^botstay_-?\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(bot_leave,       pattern="^botleave_-?\\d+$"))

    # Target channel conversation
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
            WAIT_AD_LINK:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_analyze)],
            WAIT_NICHE_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_niche_details)],
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
