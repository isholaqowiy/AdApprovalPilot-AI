"""
app.py — AdApprovalPilot AI
Main bot entry point. AdApprovalPilot AI — Full Compliance Engine.
"""
import os
import logging
import asyncio
import sqlite3
import re
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import TelegramError

# Local modules
from ai_engine import (
    analyze_channel,
    generate_ad_copies,
    analyze_target_channel,
    diagnose_rejection,
    generate_full_optimization,
)
from analyzer import (
    fetch_chat_data,
    extract_username,
    detect_violations,
    analyze_profile_issues,
    calculate_risk_score,
    risk_label,
)
from fixer import fix_channel_description, fix_channel_name, fix_all_posts
from admin_control import (
    get_persistent_admin_keyboard,
    get_link_approval_keyboard,
    get_bot_join_keyboard,
    ADMIN_ID, ADMIN_USERNAME,
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
TOKEN       = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DB_PATH     = "/tmp/users.db"
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
    WAIT_JOIN_LINK,
    WAIT_TARGET_LINKS,
    WAIT_NICHE_DETAILS,
    WAIT_COPY_SOURCE,
    WAIT_COPY_DEST,
) = range(11)

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
            joined_chat   TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS link_approvals (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            link      TEXT NOT NULL,
            status    TEXT DEFAULT 'pending',
            UNIQUE(user_id, link)
        )
    """)
    for col, defn in [("joined_chat", "TEXT DEFAULT NULL")]:
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
            first_name=excluded.first_name
    """, (user_id, username or "", first_name or "", status))
    conn.commit()
    conn.close()

def get_user_status_local(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT access_status FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_joined_chat_local(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET joined_chat=? WHERE user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()

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
        INSERT INTO link_approvals (user_id, link, status) VALUES (?, ?, ?)
        ON CONFLICT(user_id, link) DO UPDATE SET status=excluded.status
    """, (user_id, link, status))
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

def fix_actions_keyboard() -> InlineKeyboardMarkup:
    """Shown after analysis — lets user choose what to fix."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Full Optimization Plan",           callback_data="full_optimization")],
        [
            InlineKeyboardButton("✏️ Fix Description",               callback_data="fix_description"),
            InlineKeyboardButton("📛 Fix Name",                      callback_data="fix_name"),
        ],
        [InlineKeyboardButton("📝 Fix Posts (Requires Admin Access)", callback_data="fix_posts")],
        [
            InlineKeyboardButton("📡 Analyse Target Channels",       callback_data="analyse_targets"),
            InlineKeyboardButton("⏭ Back to Menu",                   callback_data="back_menu"),
        ],
    ])

def usd_to_ton(usd: float) -> float:
    return round(usd * TON_PER_USD, 2)

# ─────────────────────────────────────────────
# GATE CHECKS
# ─────────────────────────────────────────────
async def gate_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query   = update.callback_query
    user_id = query.from_user.id
    if user_id == ADMIN_ID:
        return True
    status = get_user_status_local(user_id)
    if status == "disabled":
        await query.answer("🚫 Access suspended.", show_alert=True)
        await query.edit_message_text("🚫 *Access Suspended.*\n\nContact @BlockSavvyMx.", parse_mode="Markdown")
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
    if user_id != ADMIN_ID and get_user_status_local(user_id) == "disabled":
        await update.message.reply_text("🚫 Access suspended. Contact admin @BlockSavvyMx.")
        return True
    return False

async def link_access_check(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str) -> bool:
    """Multi-link approval gate."""
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True

    status = get_link_status(user_id, link)
    if status == "approved":
        return True
    if status == "pending":
        await update.message.reply_text(
            "⏳ *Approval Pending*\n\n"
            f"Your request to analyse `{link}` is awaiting admin approval.",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return False
    if status == "denied":
        await update.message.reply_text(
            "❌ *Link Access Denied*\n\nAdmin denied this link. Contact @BlockSavvyMx.",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return False

    # New link — request admin approval
    upsert_link_request(user_id, link, "pending")
    safe_link = re.sub(r'[^a-zA-Z0-9]', '', link)[:50]
    context.bot_data[f"link_req_{user_id}_{safe_link}"] = link

    from admin_control import get_user_info
    user_info = get_user_info(user_id)
    uname = user_info[0] if user_info else "N/A"
    fname = user_info[1] if user_info else "N/A"

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔗 *New Link Request*\n\n"
                f"👤 {fname} | @{uname}\n"
                f"🆔 `{user_id}`\n"
                f"🔗 `{link}`"
            ),
            parse_mode="Markdown",
            reply_markup=get_link_approval_keyboard(user_id, safe_link)
        )
    except Exception as e:
        logger.error(f"Link notify failed: {e}")

    await update.message.reply_text(
        "📨 *Approval Requested*\n\n"
        f"Request to analyse `{link}` sent to admin.\n"
        "You'll be notified once approved.",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return False

# ─────────────────────────────────────────────
# DEEP ANALYSIS RUNNER
# ─────────────────────────────────────────────
async def run_deep_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: str,
    entity_type: str,
):
    """Full AdApprovalPilot AI compliance analysis using real Telegram data."""
    username = extract_username(link)
    user_id  = update.effective_user.id

    await update.message.reply_text(
        f"🔍 *AdApprovalPilot AI* is fetching real data for `@{username}`...\n"
        "Please wait while we run a full compliance check.",
        parse_mode="Markdown"
    )

    # 1. Fetch real data
    chat_data = await fetch_chat_data(context.bot, username)

    if not chat_data["success"]:
        err = chat_data.get("error", "")
        if "private_or_restricted" in str(err):
            await update.message.reply_text(
                "🔒 *Private or Restricted*\n\n"
                "Cannot access this channel. Make it public or use "
                "*🔧 Allow Bot to Fix* to add me as admin.",
                parse_mode="Markdown", reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "⚠️ *Cannot Access Channel*\n\nVerify the link is correct and the channel is public.",
                parse_mode="Markdown", reply_markup=main_menu_keyboard()
            )
        return

    # 2. Rule-based detection (fast, accurate)
    description     = chat_data.get("description") or ""
    violations      = detect_violations(description)
    profile_issues  = analyze_profile_issues(username, entity_type)
    risk_score      = calculate_risk_score(
        chat_data["member_count"],
        chat_data["has_description"],
        chat_data["has_photo"],
        profile_issues,
        violations,
    )

    # 3. AdApprovalPilot AI deep analysis (unique per channel) — run in executor to avoid blocking
    await update.message.reply_text("🔍 *AdApprovalPilot AI* is analyzing your channel/group/bot...", parse_mode="Markdown")

    loop        = asyncio.get_event_loop()
    ai_analysis = await loop.run_in_executor(None, lambda: analyze_channel(
        name               = chat_data["name"],
        username           = username,
        description        = description,
        member_count       = chat_data["member_count"],
        entity_type        = entity_type,
        detected_violations= violations,
        has_photo          = chat_data.get("has_photo", False),
        chat_type          = chat_data.get("chat_type", ""),
    ))

    # 4. AdApprovalPilot AI root cause diagnosis — also run in executor
    ai_diagnosis = await loop.run_in_executor(None, lambda: diagnose_rejection(
        name              = chat_data["name"],
        username          = username,
        description       = description,
        member_count      = chat_data["member_count"],
        profile_issues    = [desc for _, desc, _ in profile_issues],
        content_violations= violations,
        has_photo         = chat_data.get("has_photo", False),
    ))

    # 5. Build structured report header (real data)
    emoji  = {"channel": "📊", "group": "👥", "bot": "🤖"}.get(entity_type, "🔍")
    subs   = f"{chat_data['member_count']:,}" if chat_data["member_count"] is not None else "Unknown"
    report = (
        f"{emoji} *Compliance Report — `@{username}`*\n"
        f"📛 {chat_data['name']}\n"
        f"👥 Subscribers: {subs}\n"
        f"📊 Risk Score: {risk_score}/100 — {risk_label(risk_score)}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if chat_data["member_count"] is not None and chat_data["member_count"] < 1000:
        report += (
            "⚠️ *Low Trust Level*\n"
            f"Only {chat_data['member_count']:,} subscribers — "
            "Telegram Ads requires stronger audience trust.\n"
            "➡️ Grow to 1,000–5,000+ before running ads.\n\n"
        )

    report += f"📋 *AdApprovalPilot AI Analysis:*\n{ai_analysis}\n\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"
    report += f"🩺 *Root Cause Diagnosis:*\n{ai_diagnosis}\n\n"
    report += "━━━━━━━━━━━━━━━━━━\n"

    # Store context for fix buttons
    context.user_data.update({
        "analysis_link":        link,
        "analysis_username":    username,
        "analysis_name":        chat_data["name"],
        "analysis_description": description,
        "analysis_entity_type": entity_type,
        "analysis_issues":      profile_issues,
        "analysis_violations":  violations,
        "analysis_has_photo":   chat_data.get("has_photo", False),
        "analysis_member_count": chat_data.get("member_count"),
    })

    # Send report + fix action buttons
    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=fix_actions_keyboard())

    # Also offer target channel analysis
    context.user_data["main_link"] = link


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
        "Powered by *AdApprovalPilot AI* for expert-level, unique analysis.\n\n"
        "🚀 Request access below to get started.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

# ─────────────────────────────────────────────
# FIX BUTTONS
# ─────────────────────────────────────────────
async def full_optimization_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    data         = context.user_data
    name         = data.get("analysis_name", "")
    username     = data.get("analysis_username", "")
    description  = data.get("analysis_description", "")
    entity_type  = data.get("analysis_entity_type", "channel")
    profile_issues = data.get("analysis_issues", [])
    violations   = data.get("analysis_violations", {})
    has_photo    = data.get("analysis_has_photo", False)
    member_count = data.get("analysis_member_count")

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🚀 *AdApprovalPilot AI* is generating your full optimization plan...",
        parse_mode="Markdown"
    )

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: generate_full_optimization(
        name             = name,
        username         = username,
        description      = description,
        member_count     = member_count,
        entity_type      = entity_type,
        detected_violations = violations,
        has_photo        = has_photo,
        profile_issues   = [desc for _, desc, _ in profile_issues] if profile_issues and isinstance(profile_issues[0], tuple) else profile_issues,
    ))

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=(
            f"🚀 *Full Optimization Plan — @{username}*\n\n"
            f"{result}\n\n"
            "📋 Apply all changes above for the highest Telegram Ads approval probability."
        ),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


async def fix_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    data = context.user_data
    name        = data.get("analysis_name", "")
    username    = data.get("analysis_username", "")
    description = data.get("analysis_description", "")
    entity_type = data.get("analysis_entity_type", "channel")

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🔍 *AdApprovalPilot AI* is generating a unique, compliant description...",
            parse_mode="Markdown"
    )

    violations  = data.get("analysis_violations", {})
    has_photo   = data.get("analysis_has_photo", False)
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: fix_channel_description(name, username, description, entity_type))

    if result["compliant"]:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=result["result"],
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=(
                f"✏️ *AI-Generated Description Fix:*\n\n"
                f"_{result['result']}_\n\n"
                "📋 Copy this and update your channel description via Telegram settings."
            ),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )


async def fix_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    data = context.user_data
    name        = data.get("analysis_name", "")
    username    = data.get("analysis_username", "")
    entity_type = data.get("analysis_entity_type", "channel")
    issues      = data.get("analysis_issues", [])

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🔍 *AdApprovalPilot AI* is generating compliant name alternatives...",
            parse_mode="Markdown"
    )

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: fix_channel_name(name, username, entity_type, issues))

    if result["compliant"]:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=result["result"],
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=(
                f"📛 *AI-Generated Name Alternatives:*\n\n"
                f"{result['result']}\n\n"
                "📋 Choose one and update via Telegram channel settings."
            ),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )


async def fix_posts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=(
            "📝 *Post Fix System*\n\n"
            "To fix posts, I need admin access to your channel.\n\n"
            "Use *🔧 Allow Bot to Fix My Channel/Group* to add me as admin.\n"
            "Once added, I can scan all posts and rewrite non-compliant ones using AI."
        ),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


async def skip_fix_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📡 Analyse Target Channels", callback_data="analyse_targets"),
        InlineKeyboardButton("⏭ Back to Menu",             callback_data="back_menu"),
    ]])
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="Would you like to analyse your target channels next?",
        reply_markup=keyboard
    )

async def back_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="✅ Use /start to return to the main menu.",
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

    status = get_user_status_local(user.id)
    if status == "disabled":
        await query.edit_message_text("🚫 Access suspended. Contact @BlockSavvyMx.", reply_markup=main_menu_keyboard())
        return

    upsert_user(user.id, user.username, user.first_name,
                status if status in ("approved", "disabled") else "pending")

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 *Access Request*\n\n"
                f"👤 {user.first_name}\n"
                f"🆔 `{user.id}`\n"
                f"📛 @{user.username or 'N/A'}\n"
                f"📊 Status: `{status or 'new'}`"
            ),
            parse_mode="Markdown",
            reply_markup=get_persistent_admin_keyboard(user.id)
        )
        msg = (
            "✅ You already have access. Re-notification sent to admin."
            if status == "approved"
            else "⏳ *Request sent!*\n\nAdmin will review and notify you."
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Admin notify failed: {e}")
        await query.edit_message_text("⚠️ Could not reach admin. Try again.", reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────────
# ADMIN DECISIONS
# ─────────────────────────────────────────────
async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return

    from admin_control import (
        set_user_status, reset_user_links, get_joined_chat, clear_joined_chat
    )

    parts     = query.data.split("_", 1)
    action    = parts[0]
    target_id = int(parts[1])

    status_map = {
        "accept":  ("approved", "✅ Approved"),
        "deny":    ("denied",   "❌ Denied"),
        "disable": ("disabled", "🚫 Disabled"),
    }

    if action in status_map:
        new_status, label = status_map[action]
        set_user_status(target_id, new_status)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{label}. User `{target_id}`.\n\n_Admin panel:_",
            parse_mode="Markdown",
            reply_markup=get_persistent_admin_keyboard(target_id)
        )
        user_msgs = {
            "approved": "✅ *Access Granted!*\n\nYou now have full access.\nUse /start to open the menu.\n\n📌 Each new link requires separate admin approval.",
            "denied":   "❌ *Access Denied.*\n\nContact @BlockSavvyMx if this is a mistake.",
            "disabled": "🚫 *Access suspended by admin.*\n\nContact @BlockSavvyMx to appeal.",
        }
        try:
            await context.bot.send_message(chat_id=target_id, text=user_msgs[new_status], parse_mode="Markdown")
        except Exception:
            pass

    elif action == "reset":
        set_user_status(target_id, "pending")
        reset_user_links(target_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔁 User `{target_id}` reset. All links cleared.\n\n_Admin panel:_",
            parse_mode="Markdown",
            reply_markup=get_persistent_admin_keyboard(target_id)
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🔁 *Access reset.*\n\nPlease request access again via /start.",
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
                    text=f"🗑 Bot left chat `{joined}`.\n\n_Admin panel:_",
                    parse_mode="Markdown",
                    reply_markup=get_persistent_admin_keyboard(target_id)
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ Could not leave chat: {e}",
                    parse_mode="Markdown",
                    reply_markup=get_persistent_admin_keyboard(target_id)
                )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"ℹ️ No active chat for user `{target_id}`.\n\n_Admin panel:_",
                parse_mode="Markdown",
                reply_markup=get_persistent_admin_keyboard(target_id)
            )


# ─────────────────────────────────────────────
# LINK DECISIONS
# ─────────────────────────────────────────────
async def link_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return

    from admin_control import set_link_status

    parts     = query.data.split("_", 2)
    action    = parts[0]
    target_id = int(parts[1])
    safe_link = parts[2]
    full_link = context.bot_data.get(f"link_req_{target_id}_{safe_link}", f"https://t.me/{safe_link}")

    if action == "approvelink":
        set_link_status(target_id, full_link, "approved")
        await query.edit_message_text(f"✅ Link approved for `{target_id}`.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text=f"✅ *Link Approved!*\n\n`{full_link}`\n\nUse the Index button to proceed.",
            parse_mode="Markdown"
        )
    else:
        set_link_status(target_id, full_link, "denied")
        await query.edit_message_text(f"❌ Link denied for `{target_id}`.", parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=target_id,
            text=f"❌ *Link Denied*\n\n`{full_link}`\n\nContact @BlockSavvyMx for more info.",
            parse_mode="Markdown"
        )


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
    if not extract_username(link):
        await update.message.reply_text("⚠️ Invalid link. Send a valid `https://t.me/username` link.", parse_mode="Markdown")
        return WAIT_CHANNEL_LINK
    if not await link_access_check(update, context, link):
        return ConversationHandler.END
    await run_deep_analysis(update, context, link, "channel")
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
    if not extract_username(link):
        await update.message.reply_text("⚠️ Invalid link.", parse_mode="Markdown")
        return WAIT_GROUP_LINK
    if not await link_access_check(update, context, link):
        return ConversationHandler.END
    await run_deep_analysis(update, context, link, "group")
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
    link     = update.message.text.strip()
    username = extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link.", parse_mode="Markdown")
        return WAIT_BOT_LINK
    if not await link_access_check(update, context, link):
        return ConversationHandler.END
    await run_deep_analysis(update, context, link, "bot")
    return ConversationHandler.END


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
            "Send target channels (one per line):\n"
            "`https://t.me/channel1`\n"
            "`https://t.me/channel2`\n\n"
            "Or /cancel to return."
        ),
        parse_mode="Markdown"
    )
    return WAIT_TARGET_LINKS

async def analyse_targets_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    lines = [l.strip() for l in update.message.text.strip().split("\n") if l.strip()]
    if not lines:
        await update.message.reply_text("⚠️ No links found. Send at least one.")
        return WAIT_TARGET_LINKS

    await update.message.reply_text(f"🔍 *AdApprovalPilot AI* is analysing {len(lines)} target channel(s)...", parse_mode="Markdown")
    report = "📡 *Target Channel Risk Report*\n_(AdApprovalPilot AI — real data analysis)_\n\n"

    for link in lines:
        username = extract_username(link)
        if not username:
            report += f"⚠️ Invalid: `{link}` — skipped\n\n━━━━━━━━━━━━━━━━━━\n\n"
            continue

        chat_data = await fetch_chat_data(context.bot, username)
        if not chat_data["success"]:
            report += (
                f"🎯 `@{username}`\n"
                "⚠️ Private/restricted — cannot access.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
            )
            continue

        violations = detect_violations(chat_data.get("description") or "")
        subs       = chat_data["member_count"]

        _loop      = asyncio.get_event_loop()
        ai_result  = await _loop.run_in_executor(None, lambda: analyze_target_channel(
            name               = chat_data["name"],
            username           = username,
            description        = chat_data.get("description") or "",
            member_count       = subs,
            detected_violations= violations,
        ))

        report += f"🎯 *@{username}*  |  {chat_data['name']}\n"
        if subs is not None:
            report += f"👥 {subs:,} subscribers\n"
        report += f"\n{ai_result}\n\n━━━━━━━━━━━━━━━━━━\n\n"
        await asyncio.sleep(0.5)

    await update.message.reply_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def skip_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="✅ Analysis complete.",
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
        "✍️ *AI Ad Text Generator*\n\n"
        "Send your channel/group/bot link.\n"
        "AI will generate 3 unique, compliant ad copies based on real channel data.\n\n"
        "Example: `https://t.me/yourchannel`",
        parse_mode="Markdown"
    )
    return WAIT_AD_LINK

async def ad_text_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    link     = update.message.text.strip()
    username = extract_username(link)
    if not username:
        await update.message.reply_text("⚠️ Invalid link.", parse_mode="Markdown")
        return WAIT_AD_LINK

    await update.message.reply_text("🔍 *AdApprovalPilot AI* is fetching channel data and generating unique ad copies...", parse_mode="Markdown")
    chat_data   = await fetch_chat_data(context.bot, username)
    description = chat_data.get("description") if chat_data["success"] else None

    if not description:
        await update.message.reply_text(
            "ℹ️ *No description found.*\n\n"
            "Please describe your channel niche for AdApprovalPilot AI to generate accurate copies.\n\n"
            "Example: 'Crypto analysis for beginners worldwide'",
            parse_mode="Markdown"
        )
        context.user_data["ad_username"]    = username
        context.user_data["ad_name"]        = chat_data.get("name", username) if chat_data["success"] else username
        context.user_data["ad_entity_type"] = (
            "bot"     if username.lower().endswith("bot") else
            "group"   if any(w in username.lower() for w in ["group", "chat", "community"]) else
            "channel"
        )
        return WAIT_NICHE_DETAILS

    entity_type = (
        "bot"     if username.lower().endswith("bot") else
        "group"   if any(w in username.lower() for w in ["group", "chat", "community"]) else
        "channel"
    )
    name   = chat_data.get("name", username) if chat_data["success"] else username
    _loop  = asyncio.get_event_loop()
    copies = await _loop.run_in_executor(None, lambda: generate_ad_copies(name, username, entity_type, description))

    await update.message.reply_text(
        f"✍️ *Ad Copies for `@{username}`*\n_(AdApprovalPilot AI — based on real channel data)_\n\n{copies}\n\n"
        "📋 A/B test all 3. Never add policy-risky phrases.",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def ad_text_niche_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    niche       = update.message.text.strip()
    username    = context.user_data.get("ad_username", "channel")
    name        = context.user_data.get("ad_name", username)
    entity_type = context.user_data.get("ad_entity_type", "channel")

    await update.message.reply_text("🔍 *AdApprovalPilot AI* is generating unique ad copies based on your niche...", parse_mode="Markdown")
    _loop  = asyncio.get_event_loop()
    copies = await _loop.run_in_executor(None, lambda: generate_ad_copies(name, username, entity_type, niche=niche))

    await update.message.reply_text(
        f"✍️ *Ad Copies for `@{username}`*\n_(AdApprovalPilot AI — based on niche: {niche})_\n\n{copies}",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
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
        "💰 *Ad Budget Optimizer*\n\nEnter total budget in USD:\nExample: `50`",
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
        f"💰 *Budget Report*\n\n"
        f"💵 Total: ${budget:.2f} ≈ {usd_to_ton(budget)} TON\n"
        f"📅 Duration: {duration} days\n"
        f"📆 Daily: ${daily_opt:.2f}/day ≈ {usd_to_ton(daily_opt)} TON/day\n\n"
        f"📋 *Strategy:*\n"
        f"• Days 1–3: Test 2–3 variants\n"
        f"• Days 4–7: Scale best, pause others\n"
        f"• Pause ads with CTR <1% after day 3\n\n"
        f"💡 *Tips:*\n"
        f"• Start with lower-CPM geos for better cost efficiency\n"
        f"• Use channel post as destination\n"
        f"• Set frequency cap: 2 impressions/user/day\n\n"
        f"🪙 ~{TON_PER_USD} TON/USD (verify on CoinGecko)",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
# CPM PREDICTOR
# ─────────────────────────────────────────────
CPM_TABLE = {
    "crypto":    (1.5, 3.5, "High",   "Target lower-CPM regions worldwide to reduce cost"),
    "finance":   (1.2, 3.0, "High",   "Narrow interest targeting to control costs"),
    "tech":      (0.8, 2.0, "Medium", "Mix Tier 1 and Tier 2 for balance"),
    "education": (0.5, 1.2, "Low",    "Great niche for tight budgets"),
    "gaming":    (0.6, 1.5, "Low",    "Interactive creatives work best"),
    "health":    (0.9, 2.2, "Medium", "Avoid health claims — policy-sensitive"),
    "ecommerce": (0.7, 1.8, "Medium", "Link to channel post, not website"),
    "news":      (0.4, 1.0, "Low",    "Narrow by language for quality traffic"),
    "trading":   (1.8, 4.0, "High",   "Full financial policy compliance required"),
    "nft":       (1.0, 2.5, "High",   "Avoid hype — very high rejection rate"),
    "fitness":   (0.6, 1.4, "Low",    "Narrow by specific goal"),
    "travel":    (0.5, 1.3, "Low",    "Plan around seasonal peaks"),
}

async def ad_cpm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await gate_check(update, context):
        return ConversationHandler.END
    await query.edit_message_text(
        f"📉 *CPM Predictor*\n\n"
        f"What is your niche?\n\n"
        f"Known: `{', '.join(CPM_TABLE.keys())}`\n\n"
        f"Or describe freely (e.g. 'crypto traders worldwide')",
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
        label = matched.capitalize()
    else:
        lo, hi, risk, tip = 0.6, 1.8, "Medium", "Be more specific for better targeting"
        label = "General"
    emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk, "🟡")

    await update.message.reply_text(
        f"📉 *CPM Report*\n\n"
        f"🎯 Niche: {label}\n"
        f"💵 CPM: ${lo}–${hi} (~{usd_to_ton(lo)}–{usd_to_ton(hi)} TON)\n"
        f"⚠️ Risk: {emoji} {risk}\n\n"
        f"💡 {tip}\n\n"
        f"📋 *Tips:*\n"
        f"• Tier 2 geos cut CPM 40–60%\n"
        f"• Narrow = higher CPM, better conversion\n"
        f"• Broad = lower CPM, lower quality\n"
        f"• Test 2–3 creatives before scaling\n\n"
        f"🪙 ~{TON_PER_USD} TON/USD",
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
        "1️⃣ Add me as *admin* to your channel/group\n"
        "2️⃣ Grant: Edit/Delete messages, Change info\n"
        "3️⃣ Send the link below:",
        parse_mode="Markdown"
    )
    return WAIT_JOIN_LINK

async def bot_join_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await disabled_guard(update):
        return ConversationHandler.END
    link     = update.message.text.strip()
    username = extract_username(link)
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
                "⚠️ I'm not an admin yet. Add me as admin then send the link again.",
                reply_markup=main_menu_keyboard()
            )
            return WAIT_JOIN_LINK

        set_joined_chat_local(user_id, str(chat.id))

        from admin_control import get_user_info
        user_info = get_user_info(user_id)
        uname     = user_info[0] if user_info else "N/A"

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 *Bot Added to Channel*\n\n"
                f"👤 @{uname} (`{user_id}`)\n"
                f"📢 `@{username}`\n"
                f"🆔 Chat ID: `{chat.id}`"
            ),
            parse_mode="Markdown",
            reply_markup=get_bot_join_keyboard(chat.id)
        )

        await update.message.reply_text(
            f"✅ *Bot is admin in `@{username}`!*\n\nAdmin notified.\n\n"
            "⚠️ *Apply compliance fixes automatically?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, apply fixes", callback_data=f"applyfix_{chat.id}"),
                InlineKeyboardButton("❌ No thanks",        callback_data="skip_targets"),
            ]])
        )
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Cannot verify `@{username}`. Check the link and ensure I'm admin.",
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
    await query.edit_message_text("✅ Bot is allowed to stay.", parse_mode="Markdown")

async def bot_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorised.", show_alert=True)
        return
    chat_id = int(query.data.split("_", 1)[1])
    try:
        await context.bot.leave_chat(chat_id=chat_id)
        await query.edit_message_text(f"✅ Bot left chat `{chat_id}`.", parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"⚠️ Could not leave: {e}", parse_mode="Markdown")

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
                "Follow for reliable, niche-specific updates."
            )
        )
        results.append("✅ Description updated")
    except Exception as e:
        results.append(f"⚠️ Description: {e}")
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🔧 *Fix Results:*\n\n" + "\n".join(results),
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )


# ─────────────────────────────────────────────
# CANCEL
# ─────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ─────────────────────────────────────────────
# FLASK
# ─────────────────────────────────────────────
flask_app = Flask(__name__)
ptb_app   = Application.builder().token(TOKEN).build()

# ── Persistent event loop ──
# Using asyncio.run() in the webhook route closes the loop after each request,
# which causes "Event loop is closed" errors. We create one loop and reuse it.
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    # Use the persistent loop instead of asyncio.run() which closes the loop after each call
    _loop.run_until_complete(ptb_app.process_update(update))
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def index():
    return "AdApprovalPilot AI ✅", 200


# ─────────────────────────────────────────────
# REGISTER HANDLERS
# ─────────────────────────────────────────────
def register_handlers():
    ptb_app.add_handler(CommandHandler("start", start))

    # Standalone callbacks — BEFORE ConversationHandlers
    ptb_app.add_handler(CallbackQueryHandler(req_access,             pattern="^req_access$"))
    ptb_app.add_handler(CallbackQueryHandler(admin_decision,         pattern="^(accept|deny|disable|reset|removeassets)_\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(link_decision,          pattern="^(approvelink|denylink)_\\d+_.+$"))
    ptb_app.add_handler(CallbackQueryHandler(skip_targets,           pattern="^skip_targets$"))
    ptb_app.add_handler(CallbackQueryHandler(apply_fix,              pattern="^applyfix_-?\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(bot_stay,               pattern="^botstay_-?\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(bot_leave,              pattern="^botleave_-?\\d+$"))
    ptb_app.add_handler(CallbackQueryHandler(full_optimization_handler, pattern="^full_optimization$"))
    ptb_app.add_handler(CallbackQueryHandler(fix_description_handler,   pattern="^fix_description$"))
    ptb_app.add_handler(CallbackQueryHandler(fix_name_handler,          pattern="^fix_name$"))
    ptb_app.add_handler(CallbackQueryHandler(fix_posts_handler,         pattern="^fix_posts$"))
    ptb_app.add_handler(CallbackQueryHandler(skip_fix_handler,          pattern="^skip_fix$"))
    ptb_app.add_handler(CallbackQueryHandler(back_menu_handler,         pattern="^back_menu$"))

    # Target channels
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

    # Ad Text
    ptb_app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ad_text_start, pattern="^ad_text$")],
        states={
            WAIT_AD_LINK:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_analyze)],
            WAIT_NICHE_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_text_niche_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    ))

    # Budget
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

    # Bot Join
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
_loop.run_until_complete(setup())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
