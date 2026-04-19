"""
ai_engine.py — AdApprovalPilot AI
Gemini 1.5 Flash primary engine.
Compatible with google-generativeai 0.8.6 (installed version).
Key fix: removed request_options kwarg which is NOT supported in 0.8.6
         and silently caused every call to fail with TypeError.
"""
import os
import re
import random
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# GEMINI SETUP
# ─────────────────────────────────────────────
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

if _GEMINI_KEY:
    genai.configure(api_key=_GEMINI_KEY)
    logger.info("✅ Gemini API key loaded and configured")
else:
    logger.error("❌ GEMINI_API_KEY missing from environment — all AI calls will use fallback")

_GEN_CONFIG = GenerationConfig(
    temperature=0.9,
    top_p=0.95,
    max_output_tokens=1024,
)

# Only flash — pro is slower and not needed as primary
_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro"]


def _call_gemini(prompt: str) -> str | None:
    """
    Call Gemini API. Compatible with google-generativeai==0.8.6.
    IMPORTANT: Do NOT pass request_options to generate_content —
    that parameter is not supported in 0.8.6 and causes silent TypeError failure.
    Returns the response text, or None if all models fail.
    """
    if not _GEMINI_KEY:
        logger.warning("No API key — skipping Gemini, using fallback")
        return None

    for model_name in _MODELS:
        try:
            logger.info(f"Calling Gemini model: {model_name}")
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=_GEN_CONFIG,
            )

            # ⚠️  Do NOT add request_options= here — not supported in 0.8.6
            response = model.generate_content(prompt)

            # Safely extract text — response.text raises ValueError if blocked
            try:
                text = response.text
            except ValueError as ve:
                logger.warning(f"{model_name}: response blocked or empty — {ve}")
                continue
            except AttributeError:
                logger.warning(f"{model_name}: response has no .text attribute")
                continue

            if not text or not text.strip():
                logger.warning(f"{model_name}: returned empty text")
                continue

            text = text.strip()
            if len(text) < 30:
                logger.warning(f"{model_name}: response suspiciously short ({len(text)} chars) — skipping")
                continue

            logger.info(f"✅ Gemini success via {model_name} — {len(text)} chars returned")
            return text

        except TypeError as te:
            # This is the silent killer — wrong kwargs passed to generate_content
            logger.error(f"❌ TypeError calling {model_name}: {te} — check API compatibility")
            continue
        except Exception as e:
            logger.warning(f"Gemini {model_name} error: {type(e).__name__}: {e}")
            continue

    logger.error("All Gemini models failed — using rule-based fallback")
    return None


# ─────────────────────────────────────────────
# REWRITE MAP
# ─────────────────────────────────────────────
REWRITE_MAP = {
    "earn fast":          "grow your expertise quickly",
    "make money":         "build financial value",
    "get rich":           "achieve your financial goals",
    "guaranteed":         "proven",
    "guarantee":          "trusted",
    "100%":               "highly effective",
    "no risk":            "beginner-friendly",
    "risk free":          "accessible",
    "free money":         "free resources",
    "instant profit":     "measurable results",
    "passive income":     "consistent returns",
    "work from home":     "remote opportunities",
    "double your":        "grow your",
    "click now":          "learn more",
    "act now":            "get started",
    "limited time":       "exclusive",
    "join now":           "join us",
    "don't miss":         "explore",
    "airdrop":            "token distribution",
    "fast cash":          "quick results",
    "easy money":         "accessible opportunity",
    "moon":               "growth potential",
    "pump":               "market movement",
    "signal":             "market insight",
    "crypto signal":      "market analysis",
    "forex signal":       "currency analysis",
    "financial freedom":  "financial independence",
    "secret method":      "proven strategy",
    "hack":               "smart approach",
    "unlimited":          "extensive",
    "100x":               "high-growth",
}

_TONES = [
    "professional and direct",
    "authoritative and concise",
    "informative and clear",
    "analytical and precise",
    "expert and trustworthy",
]

_COPY_ANGLES = [
    ("Educational", "Community-Focused", "Value-Driven"),
    ("Informational", "Trust-Building", "Action-Oriented"),
    ("Expert", "Engaging", "Results-Focused"),
    ("Insightful", "Professional", "Growth-Oriented"),
]


# ─────────────────────────────────────────────
# 1. CHANNEL / GROUP / BOT ANALYSIS
# ─────────────────────────────────────────────
def analyze_channel(
    name: str,
    username: str,
    description: str,
    member_count,
    entity_type: str,
    detected_violations: dict,
) -> str:
    subs = f"{member_count:,}" if member_count is not None else "not available"
    tone = random.choice(_TONES)

    v_lines = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            v_lines += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_lines = "  No violations detected in available data.\n"

    prompt = (
        f"You are a senior Telegram Ads compliance specialist at AdApprovalPilot AI.\n\n"
        f"Analyze this Telegram {entity_type} for Telegram Ads policy compliance.\n"
        f"Use a {tone} tone. Be specific to THIS channel — never give generic advice.\n\n"
        f"CHANNEL DATA:\n"
        f"Name: {name}\n"
        f"Username: @{username}\n"
        f"Description: {description if description else 'NOT SET — empty description'}\n"
        f"Subscribers: {subs}\n"
        f"Policy Signals Detected:\n{v_lines}\n"
        f"Your response MUST include all of these sections:\n\n"
        f"RISK LEVEL: (HIGH RISK / MEDIUM RISK / LOW RISK)\n"
        f"Justify with the specific data above.\n\n"
        f"ROOT CAUSE:\n"
        f"Explain in 2-3 sentences exactly why ads from this {entity_type} would be rejected.\n"
        f"Reference the actual channel name, description content, or subscriber count.\n\n"
        f"ISSUES FOUND:\n"
        f"List each specific problem. For each, explain WHY it causes ad rejection.\n"
        f"If something is compliant, say: [Section] — No issues detected.\n\n"
        f"PRIORITY FIXES (in order of urgency):\n"
        f"List 3-5 specific actions. Each must reference this channel's actual niche.\n\n"
        f"RULES:\n"
        f"- Only use data provided above\n"
        f"- Never mention Gemini, Claude, or AI\n"
        f"- Output must be unique to @{username}\n"
        f"- Do not give advice that could apply to any random channel\n"
    )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_channel_analysis(name, username, description, member_count, detected_violations, entity_type)


# ─────────────────────────────────────────────
# 2. ROOT CAUSE DIAGNOSIS
# ─────────────────────────────────────────────
def diagnose_rejection(
    name: str,
    username: str,
    description: str,
    member_count,
    profile_issues: list,
    content_violations: dict,
) -> str:
    subs   = f"{member_count:,}" if member_count is not None else "unknown"
    tone   = random.choice(_TONES)
    p_text = "\n".join(f"  - {i}" for i in profile_issues) if profile_issues else "  None"
    v_text = ""
    if content_violations:
        for cat, phrases in content_violations.items():
            v_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_text = "  None detected\n"

    prompt = (
        f"You are the compliance diagnostician at AdApprovalPilot AI.\n"
        f"Use a {tone} tone.\n\n"
        f"CHANNEL: {name} (@{username})\n"
        f"Subscribers: {subs}\n"
        f"Description: {description if description else 'NOT SET'}\n"
        f"Profile Issues:\n{p_text}\n"
        f"Content Violations:\n{v_text}\n"
        f"Write a rejection diagnosis with these exact sections:\n\n"
        f"PRIMARY REJECTION REASON:\n"
        f"The single most likely reason ads are rejected for @{username} specifically.\n\n"
        f"CONTRIBUTING FACTORS:\n"
        f"Other issues making the rejection worse.\n\n"
        f"HOW THEY COMBINE:\n"
        f"2-3 sentences explaining how these issues together reduce Telegram approval confidence.\n\n"
        f"PRIORITY ACTION PLAN:\n"
        f"Fixes in order of impact. Start with the one that most improves approval rate.\n\n"
        f"RULES:\n"
        f"- Write as a real compliance consultant speaking to a client\n"
        f"- Be specific to @{username} — not generic\n"
        f"- Never mention Gemini, Claude, or AI\n"
    )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_diagnosis(name, username, description, member_count, profile_issues, content_violations)


# ─────────────────────────────────────────────
# 3. DESCRIPTION FIXER
# ─────────────────────────────────────────────
def fix_description(
    name: str,
    username: str,
    current_description: str,
    entity_type: str,
    niche: str = "",
) -> str:
    context  = niche or current_description or name
    has_desc = bool(current_description and current_description.strip())

    if has_desc:
        prompt = (
            f"You are AdApprovalPilot AI's compliance copywriter.\n\n"
            f"TASK: Rewrite this Telegram {entity_type} description to comply with Telegram Ads policies.\n"
            f"IMPORTANT: Only fix non-compliant parts. Keep original meaning.\n\n"
            f"Channel: {name} (@{username})\n"
            f"Current Description: {current_description}\n"
            f"Niche: {context}\n\n"
            f"Rules:\n"
            f"- Maximum 255 characters\n"
            f"- Remove spam, hype, guarantees, misleading claims\n"
            f"- Keep original language and tone where compliant\n"
            f"- If already fully compliant, respond with: COMPLIANT: No changes needed.\n"
            f"- Never mention Gemini, Claude, or AI\n"
            f"- Output must match the actual niche of {name}\n\n"
            f"Return ONLY the rewritten description. No explanation. No formatting.\n"
        )
    else:
        prompt = (
            f"You are AdApprovalPilot AI's compliance copywriter.\n\n"
            f"TASK: Write a professional, policy-compliant description for this Telegram {entity_type}.\n"
            f"The current description is EMPTY.\n\n"
            f"Channel: {name} (@{username})\n"
            f"Niche: {context}\n\n"
            f"Rules:\n"
            f"- Maximum 255 characters\n"
            f"- No spam, no hype, no guarantees\n"
            f"- Match the niche of {name} precisely — infer from the channel name\n"
            f"- Professional, trustworthy tone\n"
            f"- Completely unique — not a generic template\n"
            f"- Never mention Gemini, Claude, or AI\n\n"
            f"Return ONLY the description text. No explanation. No formatting.\n"
        )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_description(name, username, current_description, entity_type, context)


# ─────────────────────────────────────────────
# 4. NAME FIXER
# ─────────────────────────────────────────────
def fix_name(
    current_name: str,
    username: str,
    entity_type: str,
    issues: list,
) -> str:
    issues_text = "\n".join(f"  - {i}" for i in issues) if issues else "  No specific issues"

    prompt = (
        f"You are AdApprovalPilot AI's naming specialist.\n\n"
        f"Suggest 3 improved names for this Telegram {entity_type}.\n\n"
        f"Current Name: {current_name}\n"
        f"Username: @{username}\n"
        f"Issues:\n{issues_text}\n\n"
        f"Requirements:\n"
        f"- Names must comply with Telegram Ads policies\n"
        f"- Must reflect the ACTUAL niche of @{username} (infer from the username)\n"
        f"- Professional, trustworthy, not spammy or misleading\n"
        f"- Each name must be meaningfully different\n"
        f"- If current name is already compliant: COMPLIANT: Current name meets policy requirements.\n"
        f"- Never mention Gemini, Claude, or AI\n\n"
        f"Format:\n"
        f"1. [Name] — [one-line reason it works]\n"
        f"2. [Name] — [one-line reason it works]\n"
        f"3. [Name] — [one-line reason it works]\n"
    )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_name_fix(current_name, username, entity_type)


# ─────────────────────────────────────────────
# 5. POST REWRITER
# ─────────────────────────────────────────────
def rewrite_post(
    post_text: str,
    channel_name: str,
    violation_categories: list,
) -> str:
    v_text = ", ".join(violation_categories) if violation_categories else "general policy concerns"

    prompt = (
        f"You are AdApprovalPilot AI's content compliance editor.\n\n"
        f"TASK: Minimally rewrite this post to comply with Telegram Ads policies.\n"
        f"Only fix non-compliant phrases. Keep original meaning and language.\n\n"
        f"Channel: {channel_name}\n"
        f"Detected Issues: {v_text}\n\n"
        f"Original Post:\n{post_text}\n\n"
        f"Rules:\n"
        f"- Preserve original language (Arabic stays Arabic, English stays English)\n"
        f"- Only modify specific phrases that violate policy\n"
        f"- Do NOT rewrite the entire post if only part is non-compliant\n"
        f"- Keep same tone and intent\n"
        f"- If already compliant: COMPLIANT: This post meets policy requirements.\n"
        f"- Never mention Gemini, Claude, or AI\n\n"
        f"Return ONLY the rewritten post. No explanation.\n"
    )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_post_rewrite(post_text, violation_categories)


# ─────────────────────────────────────────────
# 6. AD COPY GENERATOR
# ─────────────────────────────────────────────
def generate_ad_copies(
    name: str,
    username: str,
    entity_type: str,
    description: str = None,
    niche: str = None,
) -> str:
    context = description or niche or f"A Telegram {entity_type} about {name}"
    angles  = random.choice(_COPY_ANGLES)
    tone    = random.choice(_TONES)

    prompt = (
        f"You are AdApprovalPilot AI's ad copywriter.\n\n"
        f"Generate 3 unique, policy-compliant Telegram ad copies.\n\n"
        f"{entity_type.capitalize()} Name: {name}\n"
        f"Username: @{username}\n"
        f"Context: {context}\n\n"
        f"Use a {tone} tone.\n"
        f"Write 3 copies with angles: {angles[0]}, {angles[1]}, {angles[2]}.\n\n"
        f"Each copy must:\n"
        f"- Be fully compliant with Telegram Ads policies\n"
        f"- No spam, guarantees, hype, or misleading claims\n"
        f"- Be tailored to the niche of @{username}\n"
        f"- Be 1-2 sentences with a natural CTA\n"
        f"- Be completely unique to THIS channel\n"
        f"- Never mention Gemini, Claude, or AI\n\n"
        f"Format exactly:\n"
        f"📢 Copy 1 — {angles[0]}:\n[text]\n\n"
        f"📢 Copy 2 — {angles[1]}:\n[text]\n\n"
        f"📢 Copy 3 — {angles[2]}:\n[text]\n"
    )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_ad_copies(name, username, entity_type, context, angles)


# ─────────────────────────────────────────────
# 7. TARGET CHANNEL ANALYSIS
# ─────────────────────────────────────────────
def analyze_target_channel(
    name: str,
    username: str,
    description: str,
    member_count,
    detected_violations: dict,
) -> str:
    subs   = f"{member_count:,}" if member_count is not None else "unknown"
    v_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            v_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_text = "  None detected from available data.\n"

    prompt = (
        f"You are AdApprovalPilot AI's ad placement specialist.\n\n"
        f"Evaluate this channel as a Telegram ad target:\n\n"
        f"Name: {name} (@{username})\n"
        f"Subscribers: {subs}\n"
        f"Description: {description if description else 'NOT SET'}\n"
        f"Signals:\n{v_text}\n"
        f"Provide:\n\n"
        f"RISK LEVEL: HIGH RISK / MEDIUM RISK / LOW RISK\n"
        f"[One sentence justification from the data above]\n\n"
        f"PLACEMENT ISSUES:\n"
        f"[Specific issues from provided data only]\n\n"
        f"SUITABILITY:\n"
        f"[Suitable / Conditionally suitable / Not suitable — with reason]\n\n"
        f"RECOMMENDATIONS:\n"
        f"[2-3 specific improvements for @{username}]\n\n"
        f"Rules:\n"
        f"- Only use data provided\n"
        f"- Be specific to @{username}\n"
        f"- Never mention Gemini, Claude, or AI\n"
    )

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_target_analysis(name, username, description, member_count, detected_violations)


# ─────────────────────────────────────────────
# RULE-BASED FALLBACKS
# Always produce useful output when Gemini is unavailable
# ─────────────────────────────────────────────

def _fallback_channel_analysis(name, username, description, member_count, violations, entity_type) -> str:
    subs   = member_count or 0
    issues = []
    recs   = []

    if subs < 500:
        issues.append(f"🔴 Very low audience ({subs:,} subscribers) — significantly below Telegram's trust threshold")
        recs.append("Priority 1: Grow to at least 1,000 subscribers before running ads")
    elif subs < 1000:
        issues.append(f"🟡 Low subscriber base ({subs:,}) — below the 1,000-subscriber trust minimum")
        recs.append("Priority 1: Grow to 1,000+ subscribers to improve trust score")

    if not description:
        issues.append("🔴 No description set — empty descriptions are a primary rejection trigger")
        recs.append("Priority 2: Add a clear, niche-specific description immediately")
    else:
        for cat, phrases in violations.items():
            issues.append(f"🟡 Policy signal — {cat}: `{', '.join(str(p) for p in phrases[:3])}`")
            recs.append(f"Remove {cat}-related phrases from your description")

    risk = "🔴 HIGH RISK" if (len(issues) >= 3 or subs < 500) else ("🟡 MEDIUM RISK" if issues else "🟢 LOW RISK")

    lines  = [f"*Risk Level*: {risk}", "", f"*Channel*: {name} (@{username})"]
    lines += [f"*Subscribers*: {subs:,}" if member_count else "*Subscribers*: Could not fetch", ""]
    lines += ["*Issues Found:*"]
    lines += [f"  {i}" for i in issues] if issues else ["  ✅ No major issues from available data"]
    lines += ["", "*Priority Recommendations:*"]
    lines += [f"  ➡️ {r}" for r in recs] if recs else ["  ✅ Channel appears structurally compliant"]
    return "\n".join(lines)


def _fallback_diagnosis(name, username, description, member_count, profile_issues, content_violations) -> str:
    subs    = member_count or 0
    primary = []
    factors = []
    fixes   = []

    if subs < 1000:
        primary.append(f"Low subscriber count ({subs:,}) is the primary trust signal failing Telegram's review")
        fixes.append("1. Grow audience to 1,000+ subscribers immediately")
    if not description:
        primary.append("Missing description removes a critical trust signal from the channel profile")
        fixes.append("2. Add a niche-specific, policy-compliant description")
    for issue in profile_issues[:2]:
        factors.append(str(issue))
    for cat, phrases in content_violations.items():
        factors.append(f"{cat} signals: {', '.join(str(p) for p in phrases[:2])}")
        fixes.append(f"3. Remove {cat}-related content")

    result  = "*Primary Rejection Reason:*\n"
    result += "\n".join(f"  • {p}" for p in primary) if primary else "  • Multiple combined signals reducing approval confidence"
    if factors:
        result += "\n\n*Contributing Factors:*\n" + "\n".join(f"  • {f}" for f in factors)
    if fixes:
        result += "\n\n*Action Plan:*\n" + "\n".join(f"  {f}" for f in fixes)
    result += "\n\n*Combined Effect:* These factors together reduce Telegram's approval confidence significantly."
    return result


def _fallback_description(name, username, current_desc, entity_type, context) -> str:
    base       = context.replace("_", " ").strip()
    base_title = base.title() if len(base) < 30 else name.replace("_", " ").title()

    if entity_type == "channel":
        options = [
            f"{base_title} delivers expert insights and curated content for professionals who want to stay ahead. Follow for reliable, high-quality updates.",
            f"Stay informed with {base_title} — trusted analysis and practical knowledge for a focused audience. Subscribe today.",
            f"{base_title} is your go-to source for niche-specific content and insights. Join a community that values quality and accuracy.",
        ]
    elif entity_type == "group":
        options = [
            f"Join {base_title} — a professional community for knowledge exchange and growth. Connect with like-minded members in your field.",
            f"{base_title} brings together professionals for meaningful discussion and real insights. A moderated space for serious learners.",
            f"Grow your network in {base_title}. A community built on quality discussion, support, and professional development.",
        ]
    else:
        options = [
            f"{base_title} provides smart tools to boost your productivity inside Telegram. Start now and experience the difference.",
            f"Simplify your workflow with {base_title}. Fast, reliable, and built for users who want results.",
            f"{base_title} helps you work smarter with automation. Trusted by users who value efficiency and reliability.",
        ]
    return random.choice(options)


def _fallback_name_fix(current_name, username, entity_type) -> str:
    b = username.lower().replace("_", "").replace("-", "").capitalize()
    if entity_type == "channel":
        return (
            f"1. {b}Insights — Clean, niche-specific, expert positioning\n"
            f"2. {b}Hub — Trustworthy, community-focused, policy-safe\n"
            f"3. The{b}Channel — Clear, professional, easy to understand"
        )
    elif entity_type == "group":
        return (
            f"1. {b}Community — Welcoming, clear purpose\n"
            f"2. {b}Network — Professional, niche-relevant\n"
            f"3. {b}Circle — Modern, approachable, non-spammy"
        )
    else:
        return (
            f"1. {b}AssistBot — Clear function, policy-compliant\n"
            f"2. {b}HelperBot — Simple, trustworthy\n"
            f"3. {b}ProBot — Professional, Telegram convention compliant"
        )


def _fallback_post_rewrite(post_text, violation_categories) -> str:
    cleaned = post_text
    for phrase, safe in REWRITE_MAP.items():
        cleaned = re.sub(re.escape(phrase), safe, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'!{2,}', '.', cleaned)
    cleaned = re.sub(r'\?{2,}', '?', cleaned)

    def fix_caps(m):
        w = m.group(0)
        return w.capitalize() if len(w) > 3 else w
    cleaned = re.sub(r'\b[A-Z]{4,}\b', fix_caps, cleaned)
    return cleaned.strip()


def _fallback_ad_copies(name, username, entity_type, context, angles) -> str:
    b = name.replace("_", " ").title()
    if entity_type == "channel":
        return (
            f"📢 Copy 1 — {angles[0]}:\n"
            f"Stay ahead with {b} — expert content trusted by a focused, engaged audience. ➡️ Follow now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\n"
            f"Thousands rely on {b} for reliable, niche-specific insights. ➡️ Subscribe today.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n"
            f"{b} delivers practical knowledge with no filler. ➡️ Follow the channel."
        )
    elif entity_type == "group":
        return (
            f"📢 Copy 1 — {angles[0]}:\n"
            f"Connect with professionals in {b} — real discussions, genuine growth. ➡️ Join now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\n"
            f"{b} is where serious learners gather to share knowledge. ➡️ Join the community.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n"
            f"A moderated, professional space for your niche — {b}. ➡️ Come connect."
        )
    else:
        return (
            f"📢 Copy 1 — {angles[0]}:\n"
            f"Work smarter with {b} — intelligent tools inside Telegram. ➡️ Start now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\n"
            f"Save time with {b}. Built for users who want results. ➡️ Try it today.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n"
            f"{b} is trusted by thousands. Reliable and easy to use. ➡️ Get started."
        )


def _fallback_target_analysis(name, username, description, member_count, violations) -> str:
    subs  = member_count or 0
    flags = []
    recs  = []

    if subs < 500:
        flags.append(f"Very low audience ({subs:,} subscribers) — high rejection risk")
        recs.append("Grow to 1,000+ subscribers before using as ad target")
    elif subs < 1000:
        flags.append(f"Low subscriber count ({subs:,}) — below recommended minimum")
        recs.append("Aim for 5,000+ subscribers for strong placement confidence")

    if not description:
        flags.append("No description — weak profile signal")
        recs.append("Add a niche-specific, policy-compliant description")

    for cat, phrases in violations.items():
        flags.append(f"Policy signal — {cat}: {', '.join(str(p) for p in phrases[:2])}")
        recs.append(f"Remove {cat}-related content before using as ad target")

    risk    = "🔴 HIGH RISK" if (len(flags) >= 3 or subs < 500) else ("🟡 MEDIUM RISK" if flags else "🟢 LOW RISK")
    result  = f"*Risk Level*: {risk}\n\n*Placement Issues:*\n"
    result += "\n".join(f"  • {f}" for f in flags) if flags else "  ✅ No major issues"
    result += "\n\n*Suitability:* "
    result += ("Not recommended." if len(flags) >= 3 else ("Conditionally suitable." if flags else "Suitable for placement."))
    if recs:
        result += "\n\n*Recommendations:*\n" + "\n".join(f"  ➡️ {r}" for r in recs)
    return result
