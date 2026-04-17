"""
ai_engine.py
Advanced Gemini AI engine for AdApprovalPilot AI
High-quality, unique, and deep Telegram Ads analysis & fixing
"""

import os
import logging
import random
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

FALLBACK = "⚠️ AI analysis temporarily unavailable. Please try again in a moment."


# ─────────────────────────────────────────────
# CORE GEMINI CALL (UPGRADED)
# ─────────────────────────────────────────────
def _call_gemini(prompt: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-pro")

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.9,
                "top_p": 0.95,
                "top_k": 40,
            }
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return FALLBACK


# ─────────────────────────────────────────────
# GLOBAL PROMPT ENHANCER
# ─────────────────────────────────────────────
def enhance_prompt(base_prompt: str) -> str:
    tone = random.choice([
        "Use a professional consultant tone.",
        "Use a strict compliance auditor tone.",
        "Use a helpful expert advisor tone."
    ])

    return f"""
CRITICAL INSTRUCTIONS:
- Your response MUST be unique to this specific case
- Do NOT reuse wording or structure from previous responses
- Think like a human Telegram Ads expert solving a real problem
- Be specific, not generic
- Do NOT assume data that is not provided
- If data is missing, clearly state limitations
- Internally reason step-by-step before answering

{tone}

{base_prompt}
"""


# ─────────────────────────────────────────────
# CHANNEL / GROUP / BOT ANALYSIS
# ─────────────────────────────────────────────
def analyze_channel(name, username, description, member_count, entity_type, detected_violations):

    if detected_violations:
        violations_text = "\n".join(
            [f"- {k}: {', '.join(v)}" for k, v in detected_violations.items()]
        )
    else:
        violations_text = "None detected from available data."

    subs_text = f"{member_count:,}" if member_count else "Unknown"

    base_prompt = f"""
Analyze this Telegram {entity_type} for Ads approval issues:

Name: {name}
Username: @{username}
Description: {description or "Not set"}
Subscribers: {subs_text}
Detected Signals:
{violations_text}

Tasks:
1. Identify EXACT reasons ads may be rejected
2. Explain ROOT CAUSE (not surface level)
3. Check trust level (subscriber strength)
4. Identify if lack of content affects approval
5. Rate Risk: HIGH / MEDIUM / LOW
6. Give specific actionable fixes

IMPORTANT:
- If there are NO posts, clearly state:
  "No content available for analysis"
- If subscribers < 1000, explain trust issue
- If everything is fine, clearly say it's compliant

Format:
Risk Level:
Issues Found:
Root Cause:
Recommendations:
"""

    return _call_gemini(enhance_prompt(base_prompt))


# ─────────────────────────────────────────────
# DESCRIPTION FIXER
# ─────────────────────────────────────────────
def fix_description(name, username, current_description, entity_type, niche=""):

    base_prompt = f"""
Rewrite this Telegram {entity_type} description to be Ads-compliant:

Name: {name}
Username: @{username}
Current Description: {current_description or "Empty"}
Niche: {niche or "Infer from name"}

Rules:
- Max 255 characters
- No hype, no guarantees
- Professional tone
- Keep meaning but improve compliance
- If already compliant → say "COMPLIANT"

Return ONLY final description.
"""

    return _call_gemini(enhance_prompt(base_prompt))


# ─────────────────────────────────────────────
# NAME FIXER
# ─────────────────────────────────────────────
def fix_name(current_name, username, entity_type, issues):

    issues_text = "\n".join(issues) if issues else "No major issues detected."

    base_prompt = f"""
Suggest better name for Telegram {entity_type}:

Current Name: {current_name}
Username: @{username}
Issues:
{issues_text}

Rules:
- Must be compliant
- Professional & trustworthy
- Not spammy
- Give 3 unique options
- If already fine → say COMPLIANT
"""

    return _call_gemini(enhance_prompt(base_prompt))


# ─────────────────────────────────────────────
# POST REWRITER
# ─────────────────────────────────────────────
def rewrite_post(post_text, channel_name, violation_categories):

    violations = ", ".join(violation_categories) if violation_categories else "policy issues"

    base_prompt = f"""
Rewrite this post to be Ads-compliant:

Channel: {channel_name}
Post:
{post_text}

Issues:
{violations}

Rules:
- Keep meaning
- Remove violations
- Keep same language
- If already compliant → say COMPLIANT

Return ONLY rewritten post.
"""

    return _call_gemini(enhance_prompt(base_prompt))


# ─────────────────────────────────────────────
# AD COPY GENERATOR
# ─────────────────────────────────────────────
def generate_ad_copies(name, username, entity_type, description=None, niche=None):

    context = description or niche or name

    base_prompt = f"""
Generate 3 HIGH-QUALITY Telegram ad copies:

Name: {name}
Username: @{username}
Context: {context}

Rules:
- Fully compliant
- No hype / no guarantees
- 1–2 sentences each
- Each copy must feel DIFFERENT
- Include CTA

Format:
Copy 1:
Copy 2:
Copy 3:
"""

    return _call_gemini(enhance_prompt(base_prompt))


# ─────────────────────────────────────────────
# TARGET CHANNEL ANALYSIS
# ─────────────────────────────────────────────
def analyze_target_channel(name, username, description, member_count, detected_violations):

    violations = "\n".join(
        [f"- {k}: {', '.join(v)}" for k, v in detected_violations.items()]
    ) if detected_violations else "None detected"

    subs = f"{member_count:,}" if member_count else "Unknown"

    base_prompt = f"""
Analyze this target channel for Ads placement risk:

Name: {name}
Username: @{username}
Description: {description}
Subscribers: {subs}

Signals:
{violations}

Tasks:
- Assign Risk Level: HIGH / MEDIUM / LOW
- Explain WHY
- Say if safe for ads

Format:
Risk:
Reasons:
Recommendation:
"""

    return _call_gemini(enhance_prompt(base_prompt))


# ─────────────────────────────────────────────
# ROOT CAUSE DIAGNOSIS
# ─────────────────────────────────────────────
def diagnose_rejection(name, username, description, member_count, profile_issues, content_violations):

    profile = "\n".join(profile_issues) if profile_issues else "None"
    content = "\n".join(
        [f"- {k}: {', '.join(v)}" for k, v in content_violations.items()]
    ) if content_violations else "None"

    subs = f"{member_count:,}" if member_count else "Unknown"

    base_prompt = f"""
Diagnose why Telegram ads are being rejected:

Name: {name}
Username: @{username}
Description: {description}
Subscribers: {subs}

Profile Issues:
{profile}

Content Issues:
{content}

Tasks:
- Identify PRIMARY cause
- Identify SECONDARY causes
- Explain clearly
- Give priority fix order
"""

    return _call_gemini(enhance_prompt(base_prompt))
