"""
ai_engine.py — AdApprovalPilot AI
Uses the NEW google-genai SDK (google-genai>=1.0.0).
The old google-generativeai package is deprecated and broken — this fixes it.
All responses are unique per channel, powered by Gemini 2.0 Flash.
"""
import os
import re
import random
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

if _GEMINI_KEY:
    _client = genai.Client(api_key=_GEMINI_KEY)
    logger.info("✅ AdApprovalPilot AI — Gemini client initialized")
else:
    _client = None
    logger.error("❌ GEMINI_API_KEY not set — rule-based fallback will be used")

_MODEL    = "gemini-2.0-flash"
_CONFIG   = types.GenerateContentConfig(
    temperature=0.9,
    top_p=0.95,
    max_output_tokens=1500,
)

_TONES = [
    "professional and direct",
    "authoritative and concise",
    "informative and analytical",
    "expert and consultative",
    "precise and actionable",
]

_COPY_ANGLES = [
    ("Educational", "Community-Focused", "Value-Driven"),
    ("Informational", "Trust-Building", "Action-Oriented"),
    ("Expert", "Engaging", "Results-Focused"),
    ("Insightful", "Professional", "Growth-Oriented"),
]


def _call_gemini(prompt: str) -> str | None:
    """
    Call Gemini using the new google-genai SDK.
    Returns response text or None if unavailable.
    """
    if not _client:
        logger.warning("No Gemini client — using rule-based fallback")
        return None

    try:
        logger.info(f"Calling Gemini ({_MODEL})...")
        response = _client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=_CONFIG,
        )

        if not response or not response.text:
            logger.warning("Gemini returned empty response")
            return None

        text = response.text.strip()
        if len(text) < 30:
            logger.warning(f"Gemini response too short ({len(text)} chars)")
            return None

        logger.info(f"✅ Gemini success — {len(text)} chars")
        return text

    except Exception as e:
        logger.error(f"Gemini error: {type(e).__name__}: {e}")
        return None


# ─────────────────────────────────────────────
# REWRITE MAP (fallback only)
# ─────────────────────────────────────────────
REWRITE_MAP = {
    "earn fast":         "grow your expertise quickly",
    "make money":        "build financial value",
    "get rich":          "achieve your financial goals",
    "guaranteed":        "proven",
    "guarantee":         "trusted",
    "100%":              "highly effective",
    "no risk":           "beginner-friendly",
    "risk free":         "accessible",
    "free money":        "free resources",
    "instant profit":    "measurable results",
    "passive income":    "consistent returns",
    "work from home":    "remote opportunities",
    "double your":       "grow your",
    "click now":         "learn more",
    "act now":           "get started",
    "limited time":      "exclusive",
    "join now":          "join us",
    "don't miss":        "explore",
    "airdrop":           "token distribution",
    "fast cash":         "quick results",
    "easy money":        "accessible opportunity",
    "moon":              "growth potential",
    "pump":              "market movement",
    "signal":            "market insight",
    "crypto signal":     "market analysis",
    "forex signal":      "currency analysis",
    "financial freedom": "financial independence",
    "secret method":     "proven strategy",
    "unlimited":         "extensive",
    "100x":              "high-growth",
}


# ─────────────────────────────────────────────
# 1. FULL CHANNEL / GROUP / BOT COMPLIANCE ANALYSIS
# ─────────────────────────────────────────────
def analyze_channel(
    name: str,
    username: str,
    description: str,
    member_count,
    entity_type: str,
    detected_violations: dict,
    has_photo: bool = False,
    chat_type: str = "",
) -> str:
    subs = f"{member_count:,}" if member_count is not None else "unavailable"
    tone = random.choice(_TONES)

    v_lines = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            v_lines += f"  - {cat.replace('_', ' ').title()}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_lines = "  No keyword violations detected in available data.\n"

    photo_status = "Yes — profile photo is set" if has_photo else "No — profile photo is MISSING"

    prompt = (
        "You are a senior Telegram Ads compliance expert at AdApprovalPilot AI.\n\n"
        f"Perform a FULL compliance analysis for this Telegram {entity_type}.\n"
        f"Write in a {tone} tone. Every finding must reference THIS specific channel's data.\n\n"
        "=== REAL DATA FROM TELEGRAM API ===\n"
        f"Channel Name: {name}\n"
        f"Username: @{username}\n"
        f"Description: {description if description else 'NOT SET — completely empty'}\n"
        f"Subscribers/Members: {subs}\n"
        f"Profile Photo: {photo_status}\n"
        f"Entity Type: {entity_type}\n"
        f"Keyword Policy Signals Detected:\n{v_lines}"
        "===================================\n\n"
        "Your analysis MUST cover ALL of these areas:\n\n"
        "**1. TRUST & AUTHORITY SCORE**\n"
        f"Evaluate the subscriber count ({subs}) against Telegram Ads trust thresholds.\n"
        "Explain exactly how this affects ad approval chances worldwide.\n\n"
        "**2. PROFILE COMPLETENESS**\n"
        f"Assess: profile photo ({photo_status}), name quality, description quality.\n"
        "For each missing element, explain the exact impact on ad rejection.\n\n"
        "**3. CONTENT POLICY VIOLATIONS**\n"
        "Identify every policy violation from the keyword signals detected.\n"
        "For each violation, explain WHY Telegram's review system flags it.\n"
        "If no violations: confirm compliance clearly.\n\n"
        "**4. DESCRIPTION ANALYSIS**\n"
        f"Analyze: '{description if description else 'EMPTY'}'\n"
        "Check for: spam language, vague messaging, missing niche clarity, policy violations.\n\n"
        "**5. NAME ANALYSIS**\n"
        f"Analyze: '{name}'\n"
        "Check for: spammy patterns, misleading terms, policy risks, branding clarity.\n\n"
        "**6. OVERALL RISK LEVEL**\n"
        "State: 🔴 HIGH RISK / 🟡 MEDIUM RISK / 🟢 LOW RISK\n"
        "Provide a percentage estimate of current ad approval probability.\n\n"
        "**7. ROOT CAUSE OF AD REJECTION**\n"
        "Explain in 3-4 sentences exactly WHY ads from this channel are being declined.\n"
        "Be specific — reference actual data points above, not generic reasons.\n\n"
        "**8. PRIORITY ACTION PLAN**\n"
        "List fixes in order of impact (most critical first).\n"
        "Each fix must be specific to this channel's niche and actual issues.\n"
        "Include estimated improvement in approval probability for each fix.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY the data provided above\n"
        "- Never invent posts or data not shown\n"
        "- Every recommendation must be specific to @{username}'s niche\n"
        "- Do NOT give advice that applies generically to all channels\n"
        "- Never mention Gemini, Google, or AI in your response\n"
        "- Write as AdApprovalPilot AI — a real compliance service\n"
    ).replace("{username}", username)

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_channel_analysis(name, username, description, member_count, detected_violations, entity_type, has_photo)


# ─────────────────────────────────────────────
# 2. ROOT CAUSE REJECTION DIAGNOSIS
# ─────────────────────────────────────────────
def diagnose_rejection(
    name: str,
    username: str,
    description: str,
    member_count,
    profile_issues: list,
    content_violations: dict,
    has_photo: bool = False,
) -> str:
    subs   = f"{member_count:,}" if member_count is not None else "unknown"
    tone   = random.choice(_TONES)
    p_text = "\n".join(f"  - {i}" for i in profile_issues) if profile_issues else "  None detected"
    v_text = ""
    if content_violations:
        for cat, phrases in content_violations.items():
            v_text += f"  - {cat.replace('_', ' ').title()}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_text = "  None detected\n"

    prompt = (
        "You are the lead compliance diagnostician at AdApprovalPilot AI.\n"
        f"Write in a {tone} tone. Diagnose the exact reasons ads are failing for @{username}.\n\n"
        "=== CHANNEL DATA ===\n"
        f"Name: {name} (@{username})\n"
        f"Subscribers: {subs}\n"
        f"Description: {description if description else 'NOT SET'}\n"
        f"Profile Photo: {'Set' if has_photo else 'MISSING'}\n"
        f"Profile Issues:\n{p_text}\n"
        f"Content Violations:\n{v_text}"
        "====================\n\n"
        "Write a complete rejection diagnosis with these sections:\n\n"
        "**PRIMARY REJECTION REASON:**\n"
        "The single most impactful reason ads are rejected for THIS channel specifically.\n"
        "Reference actual data — subscriber count, description content, or violations found.\n\n"
        "**CONTRIBUTING FACTORS:**\n"
        "Other issues compounding the rejection. Be specific to @{username}.\n\n"
        "**HOW THESE COMBINE:**\n"
        "2-3 sentences explaining how these issues together create a pattern that\n"
        "Telegram's automated review system flags as non-compliant.\n\n"
        "**CURRENT APPROVAL PROBABILITY:**\n"
        "Estimate the current chance of ad approval (e.g., 15%, 40%, 70%).\n"
        "Explain what is dragging it down.\n\n"
        "**PRIORITY ACTION PLAN:**\n"
        "List fixes in order of impact. For each fix, state:\n"
        "- What to do\n"
        "- Why it matters\n"
        "- Expected improvement in approval probability\n\n"
        "**TIMELINE ESTIMATE:**\n"
        "How long will it realistically take to fix these issues and get ads approved?\n\n"
        "RULES:\n"
        "- Write as a real consultant speaking directly to the channel owner\n"
        "- Be specific to @{username} — not generic advice\n"
        "- Never mention Gemini, Google, or AI\n"
        "- Reference actual data points in your response\n"
    ).replace("{username}", username)

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_diagnosis(name, username, description, member_count, profile_issues, content_violations, has_photo)


# ─────────────────────────────────────────────
# 3. DESCRIPTION FIXER
# ─────────────────────────────────────────────
def fix_description(
    name: str,
    username: str,
    current_description: str,
    entity_type: str,
    niche: str = "",
    violations: dict = None,
) -> str:
    context  = niche or current_description or name
    has_desc = bool(current_description and current_description.strip())
    v_text   = ""
    if violations:
        for cat, phrases in violations.items():
            v_text += f"  - {cat.replace('_', ' ').title()}: {', '.join(str(p) for p in phrases)}\n"

    if has_desc:
        prompt = (
            "You are AdApprovalPilot AI's compliance copywriter.\n\n"
            f"TASK: Rewrite this Telegram {entity_type} description to fully comply with Telegram Ads policies.\n"
            "CRITICAL: Only fix the non-compliant parts. Preserve original meaning, niche, and language.\n\n"
            f"Channel: {name} (@{username})\n"
            f"Current Description: {current_description}\n"
            f"Niche/Context: {context}\n"
            f"Violations Detected:\n{v_text if v_text else '  None — check for subtle issues\n'}\n"
            "Requirements:\n"
            "- Maximum 255 characters\n"
            "- Remove spam, hype, guarantees, misleading claims\n"
            "- Keep original language and tone where compliant\n"
            "- Make it clear what this channel does and who it serves\n"
            "- It must feel natural, not robotic or generic\n"
            "- If already fully compliant, respond EXACTLY: COMPLIANT: No changes needed.\n"
            "- Never mention Gemini, Google, or AI\n\n"
            "Return ONLY the rewritten description. No explanation. No formatting.\n"
        )
    else:
        prompt = (
            "You are AdApprovalPilot AI's compliance copywriter.\n\n"
            f"TASK: Write a professional, policy-compliant description for this Telegram {entity_type}.\n"
            "The description is currently EMPTY — create one from scratch.\n\n"
            f"Channel: {name} (@{username})\n"
            f"Inferred Niche: {context}\n\n"
            "Requirements:\n"
            "- Maximum 255 characters\n"
            "- No spam, hype, guarantees, or misleading claims\n"
            "- Clearly explains what this channel covers and who benefits\n"
            f"- Must match the actual niche of @{username} (infer from name)\n"
            "- Professional, trustworthy, and inviting\n"
            "- Completely unique to this channel — not a generic template\n"
            "- Never mention Gemini, Google, or AI\n\n"
            "Return ONLY the description text. No explanation. No formatting.\n"
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
    issues_text = "\n".join(f"  - {i}" for i in issues) if issues else "  No specific issues detected"

    prompt = (
        "You are AdApprovalPilot AI's brand naming and compliance specialist.\n\n"
        f"Suggest 3 improved, policy-compliant names for this Telegram {entity_type}.\n\n"
        f"Current Name: {current_name}\n"
        f"Username: @{username}\n"
        f"Detected Issues:\n{issues_text}\n\n"
        "Requirements:\n"
        f"- Infer the actual niche from @{username} and suggest names that fit it\n"
        "- Each name must comply with Telegram Ads policies\n"
        "- Professional, trustworthy — not spammy or misleading\n"
        "- Each of the 3 names must take a different angle\n"
        "- If current name is already fully compliant, respond EXACTLY:\n"
        "  COMPLIANT: Current name meets Telegram Ads policy requirements.\n"
        "- Never mention Gemini, Google, or AI\n\n"
        "Format exactly:\n"
        "1. [Name] — [one-line reason it works for this niche]\n"
        "2. [Name] — [one-line reason it works for this niche]\n"
        "3. [Name] — [one-line reason it works for this niche]\n"
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
        "You are AdApprovalPilot AI's content compliance editor.\n\n"
        "TASK: Minimally rewrite this post to comply with Telegram Ads policies.\n"
        "CRITICAL: Only fix non-compliant phrases. Keep original meaning and language.\n\n"
        f"Channel: {channel_name}\n"
        f"Detected Issues: {v_text}\n\n"
        f"Original Post:\n{post_text}\n\n"
        "Rules:\n"
        "- Preserve the original language (Arabic → Arabic, English → English)\n"
        "- Only modify the specific phrases that violate policy\n"
        "- Do NOT rewrite the entire post if only one phrase is the problem\n"
        "- Keep the same tone, intent, and structure\n"
        "- If already fully compliant, respond EXACTLY:\n"
        "  COMPLIANT: This post meets Telegram Ads policy requirements.\n"
        "- Never mention Gemini, Google, or AI\n\n"
        "Return ONLY the rewritten post. No explanation.\n"
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
    context = description or niche or f"A Telegram {entity_type} about topics related to {name}"
    angles  = random.choice(_COPY_ANGLES)
    tone    = random.choice(_TONES)

    prompt = (
        "You are AdApprovalPilot AI's senior ad copywriter.\n\n"
        f"Generate 3 unique, policy-compliant Telegram ad copies for @{username}.\n\n"
        f"Channel Name: {name}\n"
        f"Username: @{username}\n"
        f"Context: {context}\n\n"
        f"Use a {tone} tone.\n"
        f"Write 3 copies with these distinct angles: {angles[0]}, {angles[1]}, {angles[2]}.\n\n"
        "Each copy must:\n"
        "- Be fully compliant with Telegram Ads content policies worldwide\n"
        "- Contain no spam, guarantees, hype, or misleading claims\n"
        f"- Be tailored specifically to the niche of @{username}\n"
        "- Be 1-2 sentences with a natural, non-pushy CTA\n"
        "- Sound like a real, professional ad — not a template\n"
        "- Be unique to THIS channel — different from any other channel's copies\n"
        "- Never mention Gemini, Google, or AI\n\n"
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
    has_photo: bool = False,
) -> str:
    subs   = f"{member_count:,}" if member_count is not None else "unknown"
    v_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            v_text += f"  - {cat.replace('_', ' ').title()}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_text = "  None detected from available data.\n"

    prompt = (
        "You are AdApprovalPilot AI's ad placement quality specialist.\n\n"
        f"Evaluate @{username} as a target channel for Telegram ad placement.\n\n"
        "=== TARGET CHANNEL DATA ===\n"
        f"Name: {name}\n"
        f"Username: @{username}\n"
        f"Subscribers: {subs}\n"
        f"Description: {description if description else 'NOT SET'}\n"
        f"Profile Photo: {'Set' if has_photo else 'MISSING'}\n"
        f"Policy Signals:\n{v_text}"
        "===========================\n\n"
        "Provide a structured evaluation:\n\n"
        "**RISK LEVEL:** 🔴 HIGH RISK / 🟡 MEDIUM RISK / 🟢 LOW RISK\n"
        "One-sentence justification from the data above.\n\n"
        "**PLACEMENT ISSUES:**\n"
        "List specific issues that could cause ad rejection if targeting this channel.\n"
        "Only include issues supported by the data provided.\n\n"
        "**AUDIENCE QUALITY:**\n"
        "Based on subscriber count and content signals, assess the audience quality.\n\n"
        "**SUITABILITY VERDICT:**\n"
        "Suitable / Conditionally Suitable / Not Suitable — with clear reasoning.\n\n"
        "**RECOMMENDATIONS:**\n"
        "2-3 specific improvements needed before this channel can be used as an ad target.\n\n"
        "Rules:\n"
        "- Only use data provided\n"
        "- Be specific to @{username}\n"
        "- Never mention Gemini, Google, or AI\n"
    ).replace("{username}", username)

    result = _call_gemini(prompt)
    if result:
        return result
    return _fallback_target_analysis(name, username, description, member_count, detected_violations, has_photo)


# ─────────────────────────────────────────────
# 8. FULL OPTIMIZATION PLAN (all fixes at once)
# ─────────────────────────────────────────────
def generate_full_optimization(
    name: str,
    username: str,
    description: str,
    member_count,
    entity_type: str,
    detected_violations: dict,
    has_photo: bool,
    profile_issues: list,
) -> str:
    subs   = f"{member_count:,}" if member_count is not None else "unavailable"
    v_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            v_text += f"  - {cat.replace('_', ' ').title()}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_text = "  None detected\n"
    p_text = "\n".join(f"  - {i}" for i in profile_issues) if profile_issues else "  None"

    prompt = (
        "You are AdApprovalPilot AI's full-service compliance optimizer.\n\n"
        f"Generate a COMPLETE optimization plan for @{username} to get Telegram Ads approved.\n\n"
        "=== CHANNEL DATA ===\n"
        f"Name: {name} (@{username})\n"
        f"Type: {entity_type}\n"
        f"Subscribers: {subs}\n"
        f"Description: {description if description else 'NOT SET — empty'}\n"
        f"Profile Photo: {'Set' if has_photo else 'MISSING'}\n"
        f"Profile Issues:\n{p_text}\n"
        f"Content Violations:\n{v_text}"
        "====================\n\n"
        "Provide ALL of the following:\n\n"
        "**OPTIMIZED CHANNEL NAME:**\n"
        f"Suggest the best compliant name for this {entity_type} based on its niche.\n"
        "If current name is fine, say: Current name is compliant.\n\n"
        "**OPTIMIZED DESCRIPTION:**\n"
        "Write a complete, policy-compliant description (max 255 chars).\n"
        "It must match the actual niche of this channel — not a generic template.\n\n"
        "**PROFILE PHOTO GUIDANCE:**\n"
        f"{'Provide specific guidance on what image would best represent this channel.' if not has_photo else 'Photo is set — confirm if it likely meets trust standards.'}\n\n"
        "**CONTENT GUIDELINES:**\n"
        "Provide 5 specific content rules this channel must follow for Telegram Ads compliance.\n"
        "Each rule must be tailored to this channel's niche.\n\n"
        "**POST TONE GUIDE:**\n"
        "Describe the exact writing style, tone, and format posts should follow.\n\n"
        "**EXPECTED OUTCOME:**\n"
        "If all optimizations above are applied, estimate:\n"
        "- New approval probability (%)\n"
        "- Timeline to first successful ad\n"
        "- Key metrics to monitor\n\n"
        "Rules:\n"
        "- Everything must be specific to @{username}'s niche\n"
        "- Never give generic advice\n"
        "- Never mention Gemini, Google, or AI\n"
        "- Write as AdApprovalPilot AI — a professional compliance service\n"
    ).replace("{username}", username)

    result = _call_gemini(prompt)
    if result:
        return result
    return (
        f"📋 *Full Optimization Plan for @{username}*\n\n"
        f"AdApprovalPilot AI recommends addressing these areas:\n\n"
        f"• Grow subscribers to 1,000+ before running ads\n"
        f"• Add a clear, niche-specific description\n"
        f"• Set a professional profile photo\n"
        f"• Remove any policy-violating language from all posts\n"
        f"• Post consistently for 2+ weeks to establish activity signals"
    )


# ─────────────────────────────────────────────
# RULE-BASED FALLBACKS
# Always produce useful output when Gemini is unavailable
# ─────────────────────────────────────────────

def _fallback_channel_analysis(name, username, description, member_count, violations, entity_type, has_photo=False) -> str:
    subs   = member_count or 0
    issues = []
    recs   = []

    if subs < 500:
        issues.append(f"🔴 Very low audience ({subs:,} subscribers) — critically below Telegram's ad trust threshold")
        recs.append("Priority 1: Grow to at least 1,000 subscribers before running any ads")
    elif subs < 1000:
        issues.append(f"🟡 Low subscriber base ({subs:,}) — below the 1,000-subscriber trust minimum")
        recs.append("Priority 1: Grow to 1,000+ subscribers to cross the trust threshold")
    elif subs < 5000:
        issues.append(f"🟡 Moderate audience ({subs:,}) — ads may be approved but with limited reach")
        recs.append("Grow to 5,000+ subscribers for optimal ad placement performance")

    if not has_photo:
        issues.append("🟡 No profile photo — missing visual trust signal")
        recs.append("Add a professional, niche-appropriate profile photo")

    if not description:
        issues.append("🔴 No description set — empty descriptions are a primary Telegram Ads rejection trigger")
        recs.append("Priority 2: Add a clear, niche-specific description immediately")
    else:
        for cat, phrases in violations.items():
            issues.append(f"🟡 Policy violation — {cat.replace('_',' ')}: `{', '.join(str(p) for p in phrases[:3])}`")
            recs.append(f"Remove {cat.replace('_',' ')}-related phrases from your content")

    risk = "🔴 HIGH RISK" if (len(issues) >= 3 or subs < 500) else ("🟡 MEDIUM RISK" if issues else "🟢 LOW RISK")
    prob = 10 if subs < 500 else (30 if subs < 1000 else (55 if issues else 80))

    lines  = [f"*Overall Risk*: {risk}", f"*Approval Probability*: ~{prob}%", ""]
    lines += [f"*{entity_type.capitalize()}*: {name} (@{username})"]
    lines += [f"*Subscribers*: {subs:,}" if member_count is not None else "*Subscribers*: Could not fetch", ""]
    lines += ["*Issues Found:*"]
    lines += [f"  {i}" for i in issues] if issues else ["  ✅ No major issues from available data"]
    lines += ["", "*Priority Recommendations:*"]
    lines += [f"  ➡️ {r}" for r in recs] if recs else ["  ✅ Channel appears structurally compliant"]
    return "\n".join(lines)


def _fallback_diagnosis(name, username, description, member_count, profile_issues, content_violations, has_photo=False) -> str:
    subs    = member_count or 0
    primary = []
    factors = []
    fixes   = []

    if subs < 1000:
        primary.append(f"Insufficient audience size ({subs:,} subscribers) fails Telegram's minimum trust threshold for ad approval")
        fixes.append("1. Grow to 1,000+ subscribers — this is the most impactful single fix")
    if not description:
        primary.append("Empty description signals an incomplete, low-quality destination to Telegram's review system")
        fixes.append("2. Add a niche-specific, policy-compliant description immediately")
    if not has_photo:
        factors.append("Missing profile photo reduces visual trust score")
        fixes.append("3. Add a professional profile photo")
    for issue in profile_issues[:2]:
        factors.append(str(issue))
    for cat, phrases in content_violations.items():
        factors.append(f"{cat.replace('_',' ')} signals detected: {', '.join(str(p) for p in phrases[:2])}")
        fixes.append(f"4. Remove all {cat.replace('_',' ')}-related content")

    result  = "*Primary Rejection Reason:*\n"
    result += "\n".join(f"  • {p}" for p in primary) if primary else "  • Multiple combined compliance signals"
    if factors:
        result += "\n\n*Contributing Factors:*\n" + "\n".join(f"  • {f}" for f in factors)
    if fixes:
        result += "\n\n*Priority Action Plan:*\n" + "\n".join(f"  {f}" for f in fixes)
    result += "\n\n*Combined Effect:* These issues together create a pattern that Telegram's review system classifies as insufficient quality for ad placement."
    return result


def _fallback_description(name, username, current_desc, entity_type, context) -> str:
    base       = context.replace("_", " ").strip()
    base_title = base.title() if len(base) < 30 else name.replace("_", " ").title()
    options    = {
        "channel": [
            f"{base_title} delivers expert insights and curated content for professionals worldwide. Follow for reliable, high-quality updates.",
            f"Stay informed with {base_title} — trusted analysis and practical knowledge for a global audience. Subscribe today.",
            f"{base_title} — your source for niche-specific content and expert insights. Join a worldwide community that values quality.",
        ],
        "group": [
            f"Join {base_title} — a professional worldwide community for knowledge exchange and growth. Connect with like-minded members.",
            f"{base_title} brings professionals together for meaningful discussion and real insights. A moderated space for serious learners.",
            f"Grow your network in {base_title}. A global community built on quality discussion and professional development.",
        ],
        "bot": [
            f"{base_title} provides smart tools to boost your productivity inside Telegram. Trusted by users worldwide.",
            f"Simplify your workflow with {base_title}. Fast, reliable, and built for results.",
            f"{base_title} — intelligent automation for Telegram users who value efficiency.",
        ],
    }
    return random.choice(options.get(entity_type, options["channel"]))


def _fallback_name_fix(current_name, username, entity_type) -> str:
    b = username.lower().replace("_", "").replace("-", "").capitalize()
    names = {
        "channel": f"1. {b}Insights — Expert positioning, niche-specific, policy-safe\n2. {b}Hub — Trustworthy, community-oriented\n3. The{b}Channel — Clear, professional, memorable",
        "group":   f"1. {b}Community — Welcoming, clear purpose\n2. {b}Network — Professional, niche-relevant\n3. {b}Circle — Modern, approachable",
        "bot":     f"1. {b}AssistBot — Clear function, policy-compliant\n2. {b}HelperBot — Simple, trustworthy\n3. {b}ProBot — Professional, Telegram convention compliant",
    }
    return names.get(entity_type, names["channel"])


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
    copies = {
        "channel": (
            f"📢 Copy 1 — {angles[0]}:\nStay ahead with {b} — expert content trusted by a worldwide, engaged audience. ➡️ Follow now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\nThousands worldwide rely on {b} for reliable, niche-specific insights. ➡️ Subscribe today.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n{b} delivers practical knowledge with no filler. Elevate your expertise. ➡️ Follow the channel."
        ),
        "group": (
            f"📢 Copy 1 — {angles[0]}:\nConnect with professionals in {b} — real discussions, genuine growth. ➡️ Join now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\n{b} is where serious learners worldwide gather to share knowledge. ➡️ Join the community.\n\n"
            f"📢 Copy 3 — {angles[2]}:\nA moderated, professional space for your niche — {b}. ➡️ Connect today."
        ),
        "bot": (
            f"📢 Copy 1 — {angles[0]}:\nWork smarter with {b} — intelligent tools inside Telegram. ➡️ Start now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\nSave time with {b}. Built for users worldwide who want results. ➡️ Try it today.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n{b} is trusted worldwide. Reliable and easy to use. ➡️ Get started."
        ),
    }
    return copies.get(entity_type, copies["channel"])


def _fallback_target_analysis(name, username, description, member_count, violations, has_photo=False) -> str:
    subs  = member_count or 0
    flags = []
    recs  = []

    if subs < 500:
        flags.append(f"Very low audience ({subs:,} subscribers) — critically low for ad targeting")
        recs.append("Channel needs 1,000+ subscribers before being used as ad target")
    elif subs < 1000:
        flags.append(f"Low subscriber count ({subs:,})")
        recs.append("Aim for 5,000+ subscribers for reliable ad placement")
    if not description:
        flags.append("No description — weak profile signal")
        recs.append("Add a niche-specific description")
    if not has_photo:
        flags.append("No profile photo — reduces trust score")
        recs.append("Add a professional profile photo")
    for cat, phrases in violations.items():
        flags.append(f"Policy signal — {cat.replace('_',' ')}: {', '.join(str(p) for p in phrases[:2])}")
        recs.append(f"Remove {cat.replace('_',' ')}-related content")

    risk    = "🔴 HIGH RISK" if (len(flags) >= 3 or subs < 500) else ("🟡 MEDIUM RISK" if flags else "🟢 LOW RISK")
    result  = f"*Risk Level*: {risk}\n\n*Placement Issues:*\n"
    result += "\n".join(f"  • {f}" for f in flags) if flags else "  ✅ No major issues detected"
    result += "\n\n*Suitability:* "
    result += "Not recommended for placement." if len(flags) >= 3 else ("Conditionally suitable — fix issues first." if flags else "Suitable for Telegram ad placement.")
    if recs:
        result += "\n\n*Recommendations:*\n" + "\n".join(f"  ➡️ {r}" for r in recs)
    return result
