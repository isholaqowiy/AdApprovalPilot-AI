"""
ai_engine.py
Gemini AI integration for AdApprovalPilot AI.
Uses gemini-1.5-flash (stable, free-tier supported model).
All outputs branded as AdApprovalPilot AI — never mentions AI or Gemini.
"""
import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# ── Configure Gemini ──
_api_key = os.getenv("GEMINI_API_KEY", "")
if _api_key:
    genai.configure(api_key=_api_key)
else:
    logger.warning("GEMINI_API_KEY not set — AI features will use fallback mode")

# Use gemini-1.5-flash: stable, fast, free-tier supported
GEMINI_MODEL = "gemini-1.5-flash"


def _call_gemini(prompt: str, fallback: str = None) -> str:
    """
    Core Gemini call with robust error handling.
    Tries gemini-1.5-flash first, falls back to gemini-1.5-pro if needed.
    Returns fallback message only if both fail.
    """
    if not _api_key:
        return fallback or _default_fallback()

    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro"]

    for model_name in models_to_try:
        try:
            model    = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini model {model_name} failed: {e}")
            continue

    # Both models failed — return provided fallback or generate rule-based one
    logger.error("All Gemini models failed")
    return fallback or _default_fallback()


def _default_fallback() -> str:
    return (
        "AdApprovalPilot AI could not complete the analysis at this moment. "
        "Please try again in a few seconds."
    )


# ─────────────────────────────────────────────
# CHANNEL / GROUP / BOT DEEP ANALYSIS
# ─────────────────────────────────────────────
def analyze_channel(
    name: str,
    username: str,
    description: str,
    member_count,
    entity_type: str,
    detected_violations: dict,
) -> str:
    violations_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            violations_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        violations_text = "  None detected in available data."

    subs_text = f"{member_count:,}" if member_count is not None else "Unknown"

    prompt = f"""
You are AdApprovalPilot AI, a senior Telegram Ads compliance expert.

Analyze this Telegram {entity_type} for Telegram Ads policy compliance:

Name: {name}
Username: @{username}
Description: {description or "Not set — empty description"}
Subscribers/Members: {subs_text}
Detected Policy Signals:
{violations_text}

Your task:
1. Diagnose the EXACT reasons this {entity_type} may face ad rejection
2. Explain each issue clearly — be specific to THIS channel, not generic
3. State the overall risk level: HIGH RISK / MEDIUM RISK / LOW RISK
4. Give 3-5 concrete, actionable recommendations tailored to this specific {entity_type}
5. If any section is already compliant, say so explicitly

Rules:
- Base analysis ONLY on the data provided above
- Do NOT invent or assume content not shown
- Write in professional, human-like tone
- Output must be unique to this specific channel
- Format with clear sections: Risk Assessment, Issues Found, Root Cause, Recommendations
- Do NOT mention Gemini, Google, or AI in your response
- Refer to yourself only as AdApprovalPilot AI if needed
"""
    fallback = (
        f"📊 *AdApprovalPilot AI Analysis for @{username}*\n\n"
        f"Based on available data:\n\n"
        + _rule_based_analysis(name, username, description, member_count, detected_violations, entity_type)
    )
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# DESCRIPTION FIXER
# ─────────────────────────────────────────────
def fix_description(
    name: str,
    username: str,
    current_description: str,
    entity_type: str,
    niche: str = "",
) -> str:
    if not current_description and not niche:
        prompt = f"""
You are AdApprovalPilot AI, a Telegram Ads compliance copywriter.

Write a professional, policy-compliant description for this Telegram {entity_type}:
Name: {name}
Username: @{username}

Rules:
- Maximum 255 characters
- No spam, no hype, no guarantees
- Clear niche-specific language based on the channel name
- Professional tone
- Unique — not a generic template
- Do NOT mention AI, Gemini, or Google

Return ONLY the new description text. No explanation, no formatting.
"""
    else:
        prompt = f"""
You are AdApprovalPilot AI, a Telegram Ads compliance copywriter.

Rewrite this Telegram {entity_type} description to be fully compliant with Telegram Ads policies:

Channel Name: {name}
Username: @{username}
Current Description: {current_description or "Empty — create from scratch"}
Niche/Context: {niche or "Infer from channel name"}

Requirements:
- Maximum 255 characters
- Remove ALL policy violations (guarantees, hype, spam, misleading claims)
- Keep the original meaning and niche intent
- Professional, non-spammy tone
- Unique to this channel — not a generic template
- If the current description is already compliant, respond with exactly:
  COMPLIANT: No changes needed.
- Do NOT mention AI, Gemini, or Google

Return ONLY the rewritten description. No explanation.
"""
    fallback = _rule_based_description_fix(name, username, current_description, entity_type, niche)
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# NAME FIXER
# ─────────────────────────────────────────────
def fix_name(
    current_name: str,
    username: str,
    entity_type: str,
    issues: list,
) -> str:
    issues_text = "\n".join(f"  - {i}" for i in issues) if issues else "  No specific issues flagged."
    prompt = f"""
You are AdApprovalPilot AI, a Telegram Ads compliance expert and brand naming specialist.

Suggest a better name for this Telegram {entity_type}:

Current Name: {current_name}
Username: @{username}
Detected Issues:
{issues_text}

Requirements:
- Must comply with Telegram Ads policies
- Must reflect the channel's actual niche (infer from username/name)
- Professional and trustworthy
- Not spammy, not misleading, not hype-driven
- Give exactly 3 name options, each on a new line
- If the current name is already compliant, respond with exactly:
  COMPLIANT: Current name meets policy requirements.
- Do NOT mention AI, Gemini, or Google

Return ONLY the 3 name suggestions or the compliant message. No explanation.
"""
    fallback = _rule_based_name_fix(current_name, username, entity_type)
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# POST REWRITER
# ─────────────────────────────────────────────
def rewrite_post(
    post_text: str,
    channel_name: str,
    violation_categories: list,
) -> str:
    violations_text = ", ".join(violation_categories) if violation_categories else "general policy concerns"
    prompt = f"""
You are AdApprovalPilot AI, a Telegram Ads compliance editor.

Rewrite this post from the Telegram channel "{channel_name}" to comply with Telegram Ads policies.

Original Post:
{post_text}

Detected Issues: {violations_text}

Rules:
- Keep the original meaning and intent
- Remove ALL policy violations
- Match the original language (if Arabic rewrite in Arabic, if English keep English)
- Do NOT change factual information
- Keep similar length to original
- If the post is already compliant, respond with exactly:
  COMPLIANT: This post meets policy requirements.
- Do NOT mention AI, Gemini, or Google

Return ONLY the rewritten post. No explanation.
"""
    fallback = _rule_based_post_rewrite(post_text, violation_categories)
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# AD COPY GENERATOR
# ─────────────────────────────────────────────
def generate_ad_copies(
    name: str,
    username: str,
    entity_type: str,
    description: str = None,
    niche: str = None,
) -> str:
    context = description or niche or f"A Telegram {entity_type} focused on {name}"
    prompt = f"""
You are AdApprovalPilot AI, a Telegram Ads copywriter specializing in policy-compliant content.

Generate 3 completely unique, policy-compliant Telegram ad copies for:

{entity_type.capitalize()} Name: {name}
Username: @{username}
Context/Description: {context}

Requirements for EACH copy:
- Fully compliant with Telegram Ads content policies
- No spam, no guarantees, no hype language
- Compelling, professional, tailored to THIS channel's niche
- Different angle for each copy: (1) informational, (2) community-focused, (3) value-driven
- Each copy: 1-2 sentences maximum with a clear CTA
- Must be UNIQUE to this specific channel
- Do NOT mention AI, Gemini, or Google

Format exactly like this:
📢 Copy 1 — Informational:
[text]

📢 Copy 2 — Community:
[text]

📢 Copy 3 — Value:
[text]
"""
    fallback = _rule_based_ad_copies(name, username, entity_type, context)
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# TARGET CHANNEL RISK ANALYSIS
# ─────────────────────────────────────────────
def analyze_target_channel(
    name: str,
    username: str,
    description: str,
    member_count,
    detected_violations: dict,
) -> str:
    violations_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            violations_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        violations_text = "  None detected from available data."

    subs = f"{member_count:,}" if member_count is not None else "Unknown"

    prompt = f"""
You are AdApprovalPilot AI, a Telegram Ads placement specialist.

Evaluate this target channel for ad placement risk:

Name: {name}
Username: @{username}
Description: {description or "Not set"}
Subscribers: {subs}
Detected Signals:
{violations_text}

Provide:
1. Risk Level: HIGH RISK / MEDIUM RISK / LOW RISK with a one-line justification
2. Specific reasons this channel could cause ad rejection (based ONLY on provided data)
3. Whether it is suitable for Telegram Ads placement
4. 2-3 specific, actionable recommendations if improvements are needed

Base assessment ONLY on data provided.
Be specific to this channel — not generic advice.
Do NOT mention AI, Gemini, or Google.
Format: Risk Assessment → Reasons → Recommendation
"""
    fallback = _rule_based_target_analysis(name, username, description, member_count, detected_violations)
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# ROOT CAUSE DIAGNOSIS
# ─────────────────────────────────────────────
def diagnose_rejection(
    name: str,
    username: str,
    description: str,
    member_count,
    profile_issues: list,
    content_violations: dict,
) -> str:
    profile_text = "\n".join(f"  - {i}" for i in profile_issues) if profile_issues else "  None"
    violations_text = ""
    if content_violations:
        for cat, phrases in content_violations.items():
            violations_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        violations_text = "  None detected"

    subs = f"{member_count:,}" if member_count is not None else "Unknown"

    prompt = f"""
You are AdApprovalPilot AI, a senior Telegram Ads policy specialist.

A Telegram advertiser's ads keep getting rejected. Diagnose exactly WHY based on this data:

Channel Name: {name}
Username: @{username}
Description: {description or "Not set"}
Subscribers: {subs}
Profile Issues:
{profile_text}
Content Policy Signals:
{violations_text}

Write a professional diagnosis explaining:
1. The most likely PRIMARY reason for rejection
2. Secondary contributing factors
3. How these factors combine to reduce Telegram's approval confidence
4. Priority order for fixing issues (most critical first)

Write as a real compliance consultant explaining to a client.
Be specific to THIS channel.
Use plain English, not jargon.
Do NOT mention AI, Gemini, or Google.
"""
    fallback = _rule_based_diagnosis(name, username, description, member_count, profile_issues, content_violations)
    return _call_gemini(prompt, fallback)


# ─────────────────────────────────────────────
# RULE-BASED FALLBACKS (used when Gemini fails)
# These ensure the bot ALWAYS responds with useful content
# ─────────────────────────────────────────────

REWRITE_MAP = {
    "earn fast": "grow your expertise quickly",
    "make money": "build financial value",
    "get rich": "achieve your goals",
    "guaranteed": "proven",
    "guarantee": "trusted",
    "100%": "highly effective",
    "no risk": "beginner-friendly",
    "risk free": "accessible",
    "free money": "free resources",
    "instant profit": "measurable results",
    "passive income": "consistent returns",
    "work from home": "remote opportunities",
    "double your": "grow your",
    "click now": "learn more",
    "act now": "get started",
    "limited time": "exclusive",
    "join now": "join us",
    "don't miss": "explore",
    "airdrop": "token distribution",
    "fast cash": "quick results",
    "easy money": "accessible opportunity",
    "moon": "growth potential",
    "pump": "market movement",
    "signal": "market insight",
    "crypto signal": "market analysis",
}


def _rule_based_analysis(name, username, description, member_count, violations, entity_type) -> str:
    lines = []
    subs  = member_count or 0

    if subs < 1000:
        lines.append(f"• Low subscriber base ({subs:,}) — below Telegram Ads trust threshold")
    if not description:
        lines.append("• No description set — empty profile reduces approval confidence")
    for cat, phrases in violations.items():
        lines.append(f"• Policy signal detected — {cat}: {', '.join(str(p) for p in phrases[:3])}")

    if not lines:
        return "No major compliance issues detected based on available data. Review post content for additional signals."

    risk = "🔴 HIGH RISK" if len(lines) >= 3 else ("🟡 MEDIUM RISK" if len(lines) >= 1 else "🟢 LOW RISK")
    result = f"*Risk Level*: {risk}\n\n*Issues Found:*\n" + "\n".join(lines)
    result += f"\n\n*Recommendations:*\n"
    if subs < 1000:
        result += "• Grow your audience to 1,000+ subscribers before running ads\n"
    if not description:
        result += "• Add a clear, niche-specific description immediately\n"
    if violations:
        result += "• Remove policy-risky phrases from description and posts\n"
    return result


def _rule_based_description_fix(name, username, current_desc, entity_type, niche) -> str:
    base   = niche or name
    base_c = base.replace("_", " ").title()
    if entity_type == "channel":
        return f"{base_c} delivers expert insights and curated content for professionals in the niche. Follow for reliable, high-quality updates that help you stay informed and ahead."
    elif entity_type == "group":
        return f"Join {base_c} — a professional community for knowledge-sharing, discussion, and growth in your field. Connect with like-minded members today."
    else:
        return f"{base_c} provides smart, automated tools to help you work more efficiently inside Telegram. Start now and experience the difference."


def _rule_based_name_fix(current_name, username, entity_type) -> str:
    base = username.lower().replace("_", "").capitalize()
    if entity_type == "channel":
        return f"1. {base}Insights\n2. {base}Hub\n3. The{base}Channel"
    elif entity_type == "group":
        return f"1. {base}Community\n2. {base}Network\n3. {base}Circle"
    else:
        return f"1. {base}AssistBot\n2. {base}HelperBot\n3. {base}ProBot"


def _rule_based_post_rewrite(post_text, violation_categories) -> str:
    import re
    cleaned = post_text
    for phrase, safe in REWRITE_MAP.items():
        cleaned = re.sub(re.escape(phrase), safe, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'!{2,}', '.', cleaned)
    cleaned = re.sub(r'\?{2,}', '?', cleaned)
    return cleaned.strip()


def _rule_based_ad_copies(name, username, entity_type, context) -> str:
    b = name.replace("_", " ").title()
    if entity_type == "channel":
        return (
            f"📢 Copy 1 — Informational:\n"
            f"Stay ahead with {b} — expert insights and curated content for a focused audience. ➡️ Follow now.\n\n"
            f"📢 Copy 2 — Community:\n"
            f"Thousands trust {b} for reliable, niche-specific content. Join them today. ➡️ Subscribe.\n\n"
            f"📢 Copy 3 — Value:\n"
            f"{b} delivers practical knowledge with no fluff. Level up your expertise. ➡️ Follow the channel."
        )
    elif entity_type == "group":
        return (
            f"📢 Copy 1 — Informational:\n"
            f"Join {b} — where professionals share insights and grow together. ➡️ Join now.\n\n"
            f"📢 Copy 2 — Community:\n"
            f"Real discussions. Expert opinions. {b} is built for serious learners. ➡️ Join today.\n\n"
            f"📢 Copy 3 — Value:\n"
            f"{b} is a moderated, professional space for your niche. Come and connect. ➡️ Join the group."
        )
    else:
        return (
            f"📢 Copy 1 — Utility:\n"
            f"Automate and simplify with {b}. Smart tools right inside Telegram. ➡️ Start now.\n\n"
            f"📢 Copy 2 — Efficiency:\n"
            f"Save time with {b}. Built for real users who want results. ➡️ Try it.\n\n"
            f"📢 Copy 3 — Trust:\n"
            f"Thousands use {b} daily. Reliable, fast, and easy. ➡️ Get started."
        )


def _rule_based_target_analysis(name, username, description, member_count, violations) -> str:
    subs  = member_count or 0
    flags = []
    recs  = []

    if subs < 1000:
        flags.append(f"Low subscriber count ({subs:,} — minimum 1,000 recommended)")
        recs.append("Grow audience to 1,000+ before using as ad target")
    if not description:
        flags.append("No description set — weak profile signal")
        recs.append("Add a niche-specific description")
    for cat, phrases in violations.items():
        flags.append(f"Policy signal: {cat} — {', '.join(str(p) for p in phrases[:2])}")
        recs.append(f"Remove {cat}-related content from the channel")

    risk = "🔴 HIGH RISK" if len(flags) >= 3 else ("🟡 MEDIUM RISK" if flags else "🟢 LOW RISK")
    result = f"*Risk Assessment*: {risk}\n"
    if flags:
        result += "\n*Reasons:*\n" + "\n".join(f"  • {f}" for f in flags)
    else:
        result += "\nNo major issues detected based on available data."
    if recs:
        result += "\n\n*Recommendations:*\n" + "\n".join(f"  ➡️ {r}" for r in recs)
    return result


def _rule_based_diagnosis(name, username, description, member_count, profile_issues, content_violations) -> str:
    primary    = []
    secondary  = []
    priorities = []

    subs = member_count or 0
    if subs < 1000:
        primary.append(f"Low subscriber base ({subs:,}) significantly reduces Telegram's trust score for this channel")
        priorities.append("1. Grow subscribers to 1,000+ immediately")
    if not description:
        primary.append("Missing description — Telegram's review system flags empty profiles as low-quality destinations")
        priorities.append("2. Add a clear, niche-specific description")
    for issue in profile_issues[:2]:
        secondary.append(str(issue))
    for cat, phrases in content_violations.items():
        secondary.append(f"{cat} signals in content: {', '.join(str(p) for p in phrases[:2])}")
        priorities.append(f"3. Remove {cat}-related content")

    result = "*Primary Rejection Reason:*\n"
    result += "\n".join(f"  • {p}" for p in primary) if primary else "  • No single dominant factor identified\n"
    if secondary:
        result += "\n\n*Contributing Factors:*\n" + "\n".join(f"  • {s}" for s in secondary)
    if priorities:
        result += "\n\n*Fix Priority Order:*\n" + "\n".join(f"  {p}" for p in priorities)
    result += (
        "\n\n*Combined Effect:* These signals together reduce Telegram's confidence "
        "in approving ads for this destination. Address the priority items above before resubmitting."
    )
    return result
