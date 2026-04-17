"""
ai_engine.py
Gemini AI integration for AdApprovalPilot AI.
All analysis, fixing, and content generation goes through here.
"""
import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

FALLBACK = "⚠️ AI analysis temporarily unavailable. Please try again in a moment."


def _call_gemini(prompt: str) -> str:
    """Core Gemini call. Returns text or fallback on error."""
    try:
        model    = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return FALLBACK


# ─────────────────────────────────────────────
# CHANNEL / GROUP / BOT ANALYSIS
# ─────────────────────────────────────────────
def analyze_channel(
    name: str,
    username: str,
    description: str,
    member_count,
    entity_type: str,
    detected_violations: dict,
) -> str:
    """
    Deep AI analysis of a channel/group/bot.
    Builds a unique, data-driven prompt per request.
    """
    violations_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            violations_text += f"  - {cat}: {', '.join(phrases)}\n"
    else:
        violations_text = "  None detected in available data."

    subs_text = f"{member_count:,}" if member_count is not None else "Unknown"

    prompt = f"""
You are a senior Telegram Ads compliance expert with deep knowledge of Telegram's advertising policies.

Analyze this {entity_type} for Telegram Ads compliance:

Name: {name}
Username: @{username}
Description: {description or "Not set"}
Subscribers/Members: {subs_text}
Detected Policy Signals: 
{violations_text}

Your task:
1. Diagnose the EXACT reasons this {entity_type} may face ad rejection
2. Explain each issue clearly in plain English — be specific, not generic
3. Rate overall risk: HIGH / MEDIUM / LOW
4. Give 3-5 concrete, actionable recommendations tailored to THIS specific {entity_type}
5. If a section is already compliant, say so explicitly — do NOT suggest unnecessary changes

Important rules:
- Base your analysis ONLY on the data provided above
- Do NOT hallucinate or assume content not shown
- Write in a professional but human-like tone
- Your output must be unique to this specific channel — not a template
- Format clearly with sections: Risk Level, Issues Found, Root Cause, Recommendations
"""
    return _call_gemini(prompt)


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
    """Generate a compliant, unique description rewrite."""
    if not current_description and not niche:
        prompt = f"""
You are a Telegram Ads compliance copywriter.

Write a professional, policy-compliant description for this Telegram {entity_type}:
Name: {name}
Username: @{username}

Rules:
- Maximum 255 characters
- No spammy phrases, guarantees, or hype
- Clear niche-specific language
- Professional tone
- Unique — do not use generic templates
- Infer the niche from the channel name/username

Return ONLY the new description text. No explanation.
"""
    else:
        prompt = f"""
You are a Telegram Ads compliance copywriter.

Rewrite this Telegram {entity_type} description to be fully compliant with Telegram Ads policies:

Channel Name: {name}
Username: @{username}
Current Description: {current_description or "Empty — create from scratch"}
Niche/Context: {niche or "Infer from name"}

Requirements:
- Maximum 255 characters
- Remove ALL policy violations (guarantees, hype, spam, misleading claims)
- Keep the original meaning and niche
- Professional, non-spammy tone
- Must be UNIQUE to this channel — not a generic template
- If the current description is already compliant, respond with:
  "COMPLIANT: No changes needed."

Return ONLY the rewritten description. No explanation.
"""
    return _call_gemini(prompt)


# ─────────────────────────────────────────────
# NAME FIXER
# ─────────────────────────────────────────────
def fix_name(
    current_name: str,
    username: str,
    entity_type: str,
    issues: list,
) -> str:
    """Generate a compliant, niche-relevant name suggestion."""
    issues_text = "\n".join(f"  - {i}" for i in issues) if issues else "  No specific issues flagged."
    prompt = f"""
You are a Telegram Ads compliance expert and brand naming specialist.

Suggest a better name for this Telegram {entity_type}:

Current Name: {current_name}
Username: @{username}
Detected Issues with Current Name:
{issues_text}

Requirements:
- Must be compliant with Telegram Ads policies
- Must reflect the channel's actual niche (infer from username/name)
- Professional and trustworthy
- Not spammy, not misleading, not hype-driven
- Give exactly 3 name options, each on a new line
- If the current name is already compliant, respond with:
  "COMPLIANT: Current name meets policy requirements."

Return ONLY the name suggestions or the compliant message. No explanation.
"""
    return _call_gemini(prompt)


# ─────────────────────────────────────────────
# POST REWRITER
# ─────────────────────────────────────────────
def rewrite_post(
    post_text: str,
    channel_name: str,
    violation_categories: list,
) -> str:
    """Rewrite a single post to be policy-compliant."""
    violations_text = ", ".join(violation_categories) if violation_categories else "general policy concerns"
    prompt = f"""
You are a Telegram Ads compliance editor.

Rewrite this post from the Telegram channel "{channel_name}" to be fully compliant with Telegram Ads policies.

Original Post:
{post_text}

Detected Issues: {violations_text}

Rules:
- Keep the original meaning and intent
- Remove ALL policy violations (spam, hype, misleading claims, guarantees)
- Match the original language (if Arabic, rewrite in Arabic; if English, keep English)
- Do NOT change factual information
- Keep similar length to the original
- If the post is already compliant, respond with:
  "COMPLIANT: This post meets policy requirements."

Return ONLY the rewritten post. No explanation.
"""
    return _call_gemini(prompt)


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
    """Generate 3 unique, policy-compliant ad copies."""
    context = description or niche or f"A Telegram {entity_type} named {name}"
    prompt = f"""
You are a Telegram Ads copywriter specializing in policy-compliant ad content.

Generate 3 completely unique, policy-compliant Telegram ad copies for:

{entity_type.capitalize()} Name: {name}
Username: @{username}
Context/Description: {context}

Requirements for EACH copy:
- Fully compliant with Telegram Ads content policies
- No spam words, no guarantees, no hype
- Compelling and professional
- Tailored specifically to THIS channel's niche
- Different angle/tone for each copy (informational, community-focused, value-driven)
- Each copy: 1-2 sentences maximum, ending with a clear CTA

Format:
Copy 1 — [Style]:
[Text]

Copy 2 — [Style]:
[Text]

Copy 3 — [Style]:
[Text]

These copies must be UNIQUE to this specific channel. Do not reuse templates.
"""
    return _call_gemini(prompt)


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
    """AI risk analysis for a target ad placement channel."""
    violations_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            violations_text += f"  - {cat}: {', '.join(phrases)}\n"
    else:
        violations_text = "  None detected from available data."

    subs = f"{member_count:,}" if member_count is not None else "Unknown"

    prompt = f"""
You are a Telegram Ads placement specialist evaluating target channels for ad suitability.

Evaluate this target channel for ad placement risk:

Name: {name}
Username: @{username}
Description: {description or "Not set"}
Subscribers: {subs}
Detected Signals:
{violations_text}

Provide:
1. Risk Level: HIGH / MEDIUM / LOW (with brief justification)
2. Specific reasons this channel could cause ad rejection or policy issues
3. Whether it is suitable for Telegram Ads placement
4. 2-3 specific recommendations if improvements are needed

Base your assessment ONLY on the data provided.
Be specific to this channel — not generic.
Format: Risk Level → Reasons → Recommendation
"""
    return _call_gemini(prompt)


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
    """Generate a deep, human-like root cause diagnosis for ad rejection."""
    profile_text = "\n".join(f"  - {i}" for i in profile_issues) if profile_issues else "  None"
    violations_text = ""
    if content_violations:
        for cat, phrases in content_violations.items():
            violations_text += f"  - {cat}: {', '.join(phrases)}\n"
    else:
        violations_text = "  None detected"

    subs = f"{member_count:,}" if member_count is not None else "Unknown"

    prompt = f"""
You are a senior Telegram Ads policy specialist performing a rejection diagnosis.

A Telegram advertiser's ads keep getting rejected. Diagnose WHY based on this data:

Channel Name: {name}
Username: @{username}
Description: {description or "Not set"}
Subscribers: {subs}
Profile Issues:
{profile_text}
Content Policy Signals:
{violations_text}

Write a clear, professional diagnosis explaining:
1. The most likely PRIMARY reason for rejection
2. Any secondary contributing factors
3. How these factors combine to reduce Telegram's approval confidence
4. Priority order for fixing issues (what to fix first)

Write this as if you are a real compliance consultant explaining to a client.
Be specific to THIS channel — not generic advice.
Use plain English, not jargon.
"""
    return _call_gemini(prompt)
