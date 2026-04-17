"""
admin_control.py
Persistent admin control panel logic for AdApprovalPilot AI.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = "/tmp/users.db"

ADMIN_ID       = 6941833127
ADMIN_USERNAME = "BlockSavvyMx"


def get_persistent_admin_keyboard(user_id: int):
    """Import here to avoid circular import with telegram."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    uid = str(user_id)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve",            callback_data=f"accept_{uid}"),
            InlineKeyboardButton("❌ Deny",               callback_data=f"deny_{uid}"),
        ],
        [
            InlineKeyboardButton("🚫 Disable",            callback_data=f"disable_{uid}"),
            InlineKeyboardButton("🔁 Reset Access",       callback_data=f"reset_{uid}"),
        ],
        [InlineKeyboardButton("🗑 Remove From Channels",  callback_data=f"removeassets_{uid}")],
    ])


def get_link_approval_keyboard(user_id: int, safe_link: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve Link", callback_data=f"approvelink_{user_id}_{safe_link}"),
        InlineKeyboardButton("❌ Deny Link",    callback_data=f"denylink_{user_id}_{safe_link}"),
    ]])


def get_bot_join_keyboard(chat_id: int):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Allow Bot to Stay", callback_data=f"botstay_{chat_id}"),
        InlineKeyboardButton("❌ Remove Bot Now",    callback_data=f"botleave_{chat_id}"),
    ]])


# ── DB Helpers ──
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

def get_user_info(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, first_name, access_status FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def reset_user_links(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM link_approvals WHERE user_id=?", (user_id,))
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

def set_link_status(user_id: int, link: str, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE link_approvals SET status=? WHERE user_id=? AND link=?",
        (status, user_id, link)
    )
    conn.commit()
    conn.close()
