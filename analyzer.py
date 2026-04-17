"""
analyzer.py
Real Telegram data fetching and rule-based violation detection.
Works alongside ai_engine.py — provides raw data, AI provides reasoning.
"""
import re
import logging
from telegram.error import TelegramError, Forbidden, BadRequest

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# VIOLATION DETECTION RULES
# ─────────────────────────────────────────────
VIOLATION_CATEGORIES = {
    "gambling": [
        "casino", "gambling", "bet ", "betting", "jackpot", "poker",
        "roulette", "slots", "bookie", "odds", "wager", "stake",
    ],
    "adult": [
        "xxx", "adult content", "18+", "nsfw", "explicit", "nude",
        "onlyfans", "escort",
    ],
    "get_rich_quick": [
        "earn fast", "get rich", "make money fast", "instant profit",
        "easy money", "fast cash", "passive income", "quit your job",
    ],
    "financial_promises": [
        "guaranteed returns", "guaranteed profit", "100% profit",
        "risk free investment", "no risk", "double your money",
        "triple your investment", "100x", "guaranteed roi",
    ],
    "crypto_hype": [
        "moon", "lambo", "to the moon", "next bitcoin", "100x coin",
        "pump", "get in early", "presale", "airdrop bonus",
        "free crypto", "crypto signal", "forex signal", "vip signal",
        "signal group", "next 100x",
    ],
    "scam_signals": [
        "ponzi", "mlm", "referral bonus", "recruit members",
        "join my team", "unlimited earning", "secret method",
        "hack the market", "insider tip",
    ],
    "affiliate_abuse": [
        "click my link", "use my code", "referral link",
        "commission", "earn per click",
    ],
    "spam_structure": [
        "join now!!!", "limited time offer!!", "act now!!",
        "don't miss out!!", "last chance!!",
    ],
}

SUSPICIOUS_LINKS = [
    r"bit\.ly", r"tinyurl", r"shorte\.st", r"cutt\.ly",
    r"gg\.gg", r"t\.cn", r"rebrand\.ly", r"is\.gd", r"ow\.ly",
]


def detect_violations(text: str) -> dict:
    """
    Scan text for policy violations by category.
    Returns ONLY categories where violations were found.
    """
    if not text:
        return {}
    t       = text.lower()
    results = {}

    for category, phrases in VIOLATION_CATEGORIES.items():
        found = [p for p in phrases if p in t]
        if found:
            results[category] = found

    found_links = [p for p in SUSPICIOUS_LINKS if re.search(p, t)]
    if found_links:
        results["suspicious_links"] = found_links

    caps_words = [w for w in text.split() if len(w) > 3 and w.isupper()]
    if len(caps_words) >= 3:
        results["excessive_caps"] = caps_words[:5]

    return results


def analyze_profile_issues(username: str, entity_type: str) -> list:
    """
    Return list of (issue_key, description, penalty) tuples for username.
    """
    issues = []
    if len(username) < 5:
        issues.append(("short_username", "Username too short (<5 chars) — reduces trust score", 20))
    if username.isupper():
        issues.append(("caps_username", "All-caps username appears spammy", 15))
    if "__" in username:
        issues.append(("double_underscore", "Double underscores signal low-quality account", 10))
    if re.search(r'\d{3,}$', username):
        issues.append(("trailing_numbers", "Trailing numbers suggest auto-generated/spam account", 10))
    for kw in ["free", "earn", "money", "profit", "win", "casino", "bet", "signal", "forex", "pump"]:
        if kw in username.lower():
            issues.append(("risky_keyword", f"`{kw}` in username is a direct Telegram Ads policy risk", 30))
            break
    if entity_type == "bot" and not username.lower().endswith("bot"):
        issues.append(("bot_naming", "Bot username should end with 'bot' per Telegram convention", 10))
    return issues


def calculate_risk_score(
    member_count,
    has_description: bool,
    has_photo: bool,
    profile_issues: list,
    violations: dict,
) -> int:
    """Calculate overall risk penalty score (0-100)."""
    score = 0
    if member_count is None:
        score += 15
    elif member_count < 500:
        score += 40
    elif member_count < 1000:
        score += 25
    elif member_count < 5000:
        score += 10

    if not has_description:
        score += 20
    if not has_photo:
        score += 10

    for _, _, penalty in profile_issues:
        score += penalty

    for cat in violations:
        score += 20

    return min(score, 100)


def risk_label(score: int) -> str:
    if score >= 60:
        return "🔴 HIGH RISK"
    elif score >= 30:
        return "🟡 MEDIUM RISK"
    return "🟢 LOW RISK"


# ─────────────────────────────────────────────
# REAL TELEGRAM DATA FETCHER
# ─────────────────────────────────────────────
async def fetch_chat_data(bot, username: str) -> dict:
    """
    Fetch ONLY real data from Telegram API.
    Never generates or assumes data.
    """
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
        "chat_id":         None,
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
            "chat_id":         chat.id,
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


def extract_username(link: str):
    """Extract @username from t.me link or @mention."""
    link = link.strip()
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", link)
    if match:
        return match.group(1)
    if link.startswith("@"):
        return link[1:]
    return None
