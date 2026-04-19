"""
ai_engine.py — AdApprovalPilot AI
Production-grade AI engine.
Primary: Gemini 1.5 Flash
Fallback: Intelligent rule-based system (always responds)
Branding: AdApprovalPilot AI only — never mentions Gemini, Claude, or AI
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
    logger.info("Gemini API configured successfully")
else:
    logger.warning("GEMINI_API_KEY not found in environment — rule-based fallback will be used")

# Generation config for unique, varied outputs
_GEN_CONFIG = GenerationConfig(
    temperature=0.9,
    top_p=0.95,
    max_output_tokens=1024,
)

_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro"]


def _call_gemini(prompt: str) -> str | None:
    """
    Attempt Gemini call. Returns text on success, None on any failure.
    Tries flash first, then pro. Runs in a thread executor to avoid
    blocking the async event loop.
    """
    if not _GEMINI_KEY:
        logger.warning("No GEMINI_API_KEY — using fallback")
        return None

    for model_name in _MODELS:
        try:
            model    = genai.GenerativeModel(
                model_name,
                generation_config=_GEN_CONFIG,
            )
            # generate_content is synchronous — safe to call directly
            # since we're already in a sync context (called from async via run_in_executor)
            response = model.generate_content(
                prompt,
                request_options={"timeout": 30},
            )
            if response is None:
                logger.warning(f"{model_name}: empty response object")
                continue
            # Access text safely
            try:
                text = response.text
            except Exception:
                # response.text raises if blocked or empty
                logger.warning(f"{model_name}: response.text inaccessible (possibly blocked)")
                continue

            if text and text.strip() and len(text.strip()) > 20:
                logger.info(f"Gemini ({model_name}) success — {len(text)} chars")
                return text.strip()
            else:
                logger.warning(f"{model_name}: response too short or empty")

        except Exception as e:
            logger.warning(f"Gemini {model_name} failed: {type(e).__name__}: {e}")
            continue

    logger.error("All Gemini models failed — rule-based fallback will be used")
    return None


def _processing_error_msg() -> str:
    """Never expose technical errors to users."""
    return (
        "AdApprovalPilot AI is processing your request. "
        "Please try again shortly."
    )


# ─────────────────────────────────────────────
# REWRITE MAP (used in rule-based fallback)
# ─────────────────────────────────────────────
REWRITE_MAP = {
    "earn fast":           "grow your expertise quickly",
    "make money":          "build financial value",
    "get rich":            "achieve your financial goals",
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
    "join now":            "join us",
    "don't miss":          "explore",
    "airdrop":             "token distribution",
    "fast cash":           "quick results",
    "easy money":          "accessible opportunity",
    "moon":                "growth potential",
    "pump":                "market movement",
    "signal":              "market insight",
    "crypto signal":       "market analysis",
    "forex signal":        "currency analysis",
    "financial freedom":   "financial independence",
    "passive income":      "recurring value",
    "secret method":       "proven strategy",
    "hack":                "smart approach",
    "unlimited":           "extensive",
    "100x":                "high-growth",
}

# ─────────────────────────────────────────────
# TONE VARIANTS (ensures uniqueness across calls)
# ─────────────────────────────────────────────
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
# 1. CHANNEL / GROUP / BOT DEEP ANALYSIS
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

    violations_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            violations_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        violations_text = "  No violations detected in available data."

    prompt = f"""
You are a senior Telegram Ads compliance specialist at AdApprovalPilot AI.

Analyze this Telegram {entity_type} for Telegram Ads policy compliance.
Use a {tone} tone. This analysis must be unique and specific to this exact channel.

--- CHANNEL DATA ---
Name: {name}
Username: @{username}
Description: {description or "NOT SET — empty description"}
Subscribers: {subs}
Detected Policy Signals:
{violations_text}
--------------------

Your analysis MUST include:

1. RISK LEVEL: State clearly — HIGH RISK / MEDIUM RISK / LOW RISK
   Justify with specific data points from above.

2. ROOT CAUSE: Explain in 2-3 sentences exactly WHY ads would be rejected.
   Be specific to THIS channel. Not generic advice.

3. ISSUES FOUND: List each problem with a brief explanation of WHY it matters for Telegram Ads.
   If a section is fully compliant, say: "✅ [Section] — No issues detected."

4. PRIORITY FIXES: List 3-5 actions in priority order, most urgent first.
   Each fix must be specific to the niche of this channel.

5. APPROVAL IMPACT: For each fix, briefly state how it improves approval chances.

Rules:
- Base ONLY on data provided above
- Never invent posts or subscribers
- If description is empty, flag it as a primary rejection risk
- Use plain, human-like English
- Do NOT mention Gemini, Claude, or AI anywhere
- Do NOT use generic advice that could apply to any channel
- Your output for @{username} must differ from any other channel analysis
"""

    result = _call_gemini(prompt)
    if result:
        return result

    # Rule-based fallback — always produces a useful, specific response
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
    subs  = f"{member_count:,}" if member_count is not None else "unknown"
    tone  = random.choice(_TONES)
    p_text = "\n".join(f"  - {i}" for i in profile_issues) if profile_issues else "  None detected"
    v_text = ""
    if content_violations:
        for cat, phrases in content_violations.items():
            v_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        v_text = "  None detected"

    prompt = f"""
You are AdApprovalPilot AI's head compliance diagnostician.
Use a {tone} tone. Write a unique rejection diagnosis for @{username}.

--- DATA ---
Channel: {name} (@{username})
Subscribers: {subs}
Description: {description or "NOT SET"}
Profile Issues:
{p_text}
Content Violations:
{v_text}
-----------

Write a clear, structured rejection diagnosis:

PRIMARY REJECTION REASON:
State the single most likely reason ads are being rejected for THIS channel.

CONTRIBUTING FACTORS:
List secondary issues that compound the primary problem.

HOW THEY COMBINE:
Explain in 2-3 sentences how these factors together reduce Telegram's approval confidence.

PRIORITY ACTION PLAN:
List fixes in order of impact. Start with the one that will most improve approval rate.

Tone: Expert compliance consultant speaking directly to a client.
Be specific to @{username} — not generic advice.
Do NOT mention Gemini, Claude, or AI.
"""

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
    context = niche or current_description or name
    has_desc = bool(current_description and current_description.strip())

    if has_desc:
        prompt = f"""
You are AdApprovalPilot AI's compliance copywriter.

TASK: Minimally rewrite this Telegram {entity_type} description to comply with Telegram Ads policies.
IMPORTANT: Only fix the non-compliant parts. Preserve as much of the original as possible.

Channel: {name} (@{username})
Current Description: {current_description}
Niche Context: {context}

Rules:
- Maximum 255 characters
- Only edit phrases that violate policy (spam, hype, guarantees, misleading claims)
- Keep original language and tone where compliant
- Do NOT replace compliant sections with generic text
- If already fully compliant, respond with EXACTLY: COMPLIANT: No changes needed.
- Do NOT mention Gemini, Claude, or AI
- Output must be specific to the niche of {name}

Return ONLY the rewritten description. No explanation. No formatting.
"""
    else:
        prompt = f"""
You are AdApprovalPilot AI's compliance copywriter.

TASK: Write a professional, policy-compliant description for this Telegram {entity_type}.
The current description is EMPTY — create one from scratch based on the channel name.

Channel: {name} (@{username})
Niche: {context}

Rules:
- Maximum 255 characters
- No spam, no hype, no guarantees, no misleading claims
- Match the niche of {name} precisely
- Professional, trustworthy tone
- Completely unique — not a generic template
- Do NOT mention Gemini, Claude, or AI

Return ONLY the description text. No explanation. No formatting.
"""

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

    prompt = f"""
You are AdApprovalPilot AI's naming specialist.

Suggest 3 improved names for this Telegram {entity_type}.

Current Name: {current_name}
Username: @{username}
Detected Issues:
{issues_text}

Requirements:
- Names must comply with Telegram Ads policies
- Must reflect the ACTUAL niche of @{username} (infer from the username)
- Professional, trustworthy, not spammy or misleading
- Each name must be meaningfully different from the others
- If the current name is already fully compliant, respond with EXACTLY:
  COMPLIANT: Current name meets policy requirements.
- Do NOT mention Gemini, Claude, or AI

Format:
1. [Name] — [one-line reason it works]
2. [Name] — [one-line reason it works]
3. [Name] — [one-line reason it works]
"""

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
    violations_text = ", ".join(violation_categories) if violation_categories else "general policy concerns"

    prompt = f"""
You are AdApprovalPilot AI's content compliance editor.

TASK: Minimally rewrite this post to comply with Telegram Ads policies.
IMPORTANT: Only fix non-compliant phrases. Keep original meaning and language.

Channel: {channel_name}
Detected Issues: {violations_text}

Original Post:
{post_text}

Rules:
- Preserve the original language (Arabic → Arabic, English → English)
- Only modify the specific phrases that violate policy
- Do NOT rewrite the entire post if only part is non-compliant
- Keep the same tone and intent as the original
- If already fully compliant, respond with EXACTLY:
  COMPLIANT: This post meets policy requirements.
- Do NOT mention Gemini, Claude, or AI

Return ONLY the rewritten post. No explanation.
"""

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
    context = description or niche or f"A Telegram {entity_type} focused on topics related to {name}"
    angles  = random.choice(_COPY_ANGLES)
    tone    = random.choice(_TONES)

    prompt = f"""
You are AdApprovalPilot AI's ad copywriter specializing in Telegram Ads policy compliance.

Generate 3 unique, policy-compliant Telegram ad copies for:

{entity_type.capitalize()} Name: {name}
Username: @{username}
Channel Context: {context}

Use a {tone} tone. Write 3 copies with these angles: {angles[0]}, {angles[1]}, {angles[2]}.

Requirements for EACH copy:
- Fully compliant with Telegram Ads content policies
- No spam, no guarantees, no hype, no misleading claims
- Tailored specifically to the niche of @{username}
- Each copy takes a different angle (see angles above)
- 1-2 sentences maximum with a natural CTA
- Must be completely unique to THIS channel
- Do NOT mention Gemini, Claude, or AI

Format exactly:
📢 Copy 1 — {angles[0]}:
[text]

📢 Copy 2 — {angles[1]}:
[text]

📢 Copy 3 — {angles[2]}:
[text]
"""

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
    subs          = f"{member_count:,}" if member_count is not None else "unknown"
    violations_text = ""
    if detected_violations:
        for cat, phrases in detected_violations.items():
            violations_text += f"  - {cat}: {', '.join(str(p) for p in phrases)}\n"
    else:
        violations_text = "  None detected from available data."

    prompt = f"""
You are AdApprovalPilot AI's ad placement specialist.

Evaluate this Telegram channel as a target for ad placement:

Name: {name} (@{username})
Subscribers: {subs}
Description: {description or "NOT SET"}
Detected Signals:
{violations_text}

Provide a structured evaluation:

RISK LEVEL: HIGH RISK / MEDIUM RISK / LOW RISK
[One sentence justification based on data above]

PLACEMENT ISSUES:
[List specific reasons this channel could cause ad rejection — based ONLY on data provided]

SUITABILITY:
[State whether this channel is suitable, conditionally suitable, or not suitable for Telegram Ads]

RECOMMENDATIONS:
[2-3 specific, actionable improvements for this exact channel]

Base assessment ONLY on provided data. Be specific to @{username}.
Do NOT mention Gemini, Claude, or AI.
"""

    result = _call_gemini(prompt)
    if result:
        return result

    return _fallback_target_analysis(name, username, description, member_count, detected_violations)


# ─────────────────────────────────────────────
# RULE-BASED FALLBACKS
# Always produce useful, specific output — never fail silently
# ─────────────────────────────────────────────

def _fallback_channel_analysis(name, username, description, member_count, violations, entity_type) -> str:
    subs   = member_count or 0
    issues = []
    recs   = []

    if subs < 500:
        issues.append(f"🔴 Very low audience ({subs:,} subscribers) — significantly below Telegram's trust threshold for ad approval")
        recs.append("Priority 1: Grow to at least 1,000 subscribers before running ads")
    elif subs < 1000:
        issues.append(f"🟡 Low subscriber base ({subs:,}) — below the 1,000-subscriber trust minimum for Telegram Ads")
        recs.append("Priority 1: Grow to 1,000+ subscribers to improve trust score")

    if not description:
        issues.append("🔴 No description set — empty descriptions are a primary rejection trigger in Telegram's review system")
        recs.append("Priority 2: Add a clear, niche-specific description immediately")
    else:
        for cat, phrases in violations.items():
            issues.append(f"🟡 Policy signal in description — {cat}: detected phrase(s): `{', '.join(str(p) for p in phrases[:3])}`")
            recs.append(f"Remove {cat}-related phrases from your description")

    risk = "🔴 HIGH RISK" if len(issues) >= 3 or subs < 500 else (
           "🟡 MEDIUM RISK" if issues else "🟢 LOW RISK")

    lines = [
        f"*Risk Level*: {risk}",
        "",
        f"*Channel*: {name} (@{username})",
        f"*Subscribers*: {subs:,}" if member_count else "*Subscribers*: Could not fetch",
        "",
        "*Issues Found:*",
    ]
    lines += [f"  {i}" for i in issues] if issues else ["  ✅ No major issues detected from available data"]
    lines += ["", "*Priority Recommendations:*"]
    lines += [f"  ➡️ {r}" for r in recs] if recs else ["  ✅ Channel appears structurally compliant"]

    return "\n".join(lines)


def _fallback_diagnosis(name, username, description, member_count, profile_issues, content_violations) -> str:
    subs    = member_count or 0
    primary = []
    factors = []
    fixes   = []

    if subs < 1000:
        primary.append(f"Low subscriber count ({subs:,}) is the primary trust signal failing Telegram's review threshold")
        fixes.append("1. Grow audience to 1,000+ subscribers immediately")
    if not description:
        primary.append("Missing description removes a critical trust signal from the channel profile")
        fixes.append("2. Add a niche-specific, policy-compliant description")
    for issue in profile_issues[:2]:
        factors.append(str(issue))
    for cat, phrases in content_violations.items():
        factors.append(f"{cat} signals: {', '.join(str(p) for p in phrases[:2])}")
        fixes.append(f"3. Remove {cat}-related content from description and posts")

    result  = "*Primary Rejection Reason:*\n"
    result += "\n".join(f"  • {p}" for p in primary) if primary else "  • Multiple combined signals reducing approval confidence"
    if factors:
        result += "\n\n*Contributing Factors:*\n" + "\n".join(f"  • {f}" for f in factors)
    if fixes:
        result += "\n\n*Action Plan (in priority order):*\n" + "\n".join(f"  {f}" for f in fixes)
    result += (
        "\n\n*Combined Effect:* These factors together signal low quality or policy risk to "
        "Telegram's automated review system, reducing approval confidence significantly."
    )
    return result


def _fallback_description(name, username, current_desc, entity_type, context) -> str:
    base = context.replace("_", " ").strip()
    base_title = base.title() if len(base) < 30 else name.replace("_", " ").title()

    if entity_type == "channel":
        templates = [
            f"{base_title} delivers expert insights and curated content for professionals who want to stay ahead in their field. Follow for reliable, high-quality updates.",
            f"Stay informed with {base_title} — trusted content, expert analysis, and practical knowledge for a focused audience. Subscribe today.",
            f"{base_title} is your go-to source for professional content and niche-specific insights. Join a community that values quality and accuracy.",
        ]
    elif entity_type == "group":
        templates = [
            f"Join {base_title} — a professional community for knowledge exchange, discussion, and growth. Connect with like-minded members in your field.",
            f"{base_title} brings together professionals for meaningful discussion and real insights. A moderated space for serious learners.",
            f"Grow your network and knowledge in {base_title}. A community built on quality discussion, mutual support, and professional development.",
        ]
    else:
        templates = [
            f"{base_title} provides smart, automated tools to boost your productivity inside Telegram. Start now and experience the difference.",
            f"Simplify your workflow with {base_title}. Fast, reliable, and built for real users who want results without complexity.",
            f"{base_title} helps you work smarter with intelligent automation. Trusted by users who value efficiency and reliability.",
        ]
    return random.choice(templates)


def _fallback_name_fix(current_name, username, entity_type) -> str:
    base = username.lower().replace("_", "").replace("-", "")
    b    = base.capitalize()
    if entity_type == "channel":
        return (
            f"1. {b}Insights — Clean, niche-specific, positions channel as expert source\n"
            f"2. {b}Hub — Trustworthy, community-focused, policy-safe\n"
            f"3. The{b}Channel — Clear, professional, easy to understand"
        )
    elif entity_type == "group":
        return (
            f"1. {b}Community — Welcoming and clearly describes purpose\n"
            f"2. {b}Network — Professional tone, niche-relevant\n"
            f"3. {b}Circle — Modern, approachable, non-spammy"
        )
    else:
        return (
            f"1. {b}AssistBot — Clear functional purpose, policy-compliant\n"
            f"2. {b}HelperBot — Simple, trustworthy, easy to remember\n"
            f"3. {b}ProBot — Professional positioning, Telegram convention compliant"
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
            f"Join thousands who rely on {b} for reliable, niche-specific insights. ➡️ Subscribe today.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n"
            f"{b} delivers practical knowledge with no filler. Elevate your expertise. ➡️ Follow the channel."
        )
    elif entity_type == "group":
        return (
            f"📢 Copy 1 — {angles[0]}:\n"
            f"Connect with professionals in {b} — real discussions, expert opinions, genuine growth. ➡️ Join now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\n"
            f"{b} is where serious learners gather to share knowledge and grow together. ➡️ Join the community.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n"
            f"A moderated, professional space built for your niche — that's {b}. ➡️ Come and connect."
        )
    else:
        return (
            f"📢 Copy 1 — {angles[0]}:\n"
            f"Work smarter with {b} — intelligent automation built right into Telegram. ➡️ Start now.\n\n"
            f"📢 Copy 2 — {angles[1]}:\n"
            f"Save time and get results with {b}. Built for users who value efficiency. ➡️ Try it today.\n\n"
            f"📢 Copy 3 — {angles[2]}:\n"
            f"{b} is trusted by thousands for reliable, fast, and easy-to-use tools. ➡️ Get started."
        )


def _fallback_target_analysis(name, username, description, member_count, violations) -> str:
    subs  = member_count or 0
    flags = []
    recs  = []

    if subs < 500:
        flags.append(f"Very low audience ({subs:,} subscribers) — high rejection risk for ad placement")
        recs.append("Grow channel to 1,000+ subscribers before using as ad target")
    elif subs < 1000:
        flags.append(f"Low subscriber count ({subs:,}) — below recommended minimum for reliable ad placement")
        recs.append("Aim for 5,000+ subscribers for strong ad placement confidence")

    if not description:
        flags.append("No description — weak profile signal reduces ad approval confidence")
        recs.append("Add a niche-specific, policy-compliant description")

    for cat, phrases in violations.items():
        flags.append(f"Policy signal detected — {cat}: {', '.join(str(p) for p in phrases[:2])}")
        recs.append(f"Remove {cat}-related content before using as ad target")

    risk = "🔴 HIGH RISK" if len(flags) >= 3 or subs < 500 else (
           "🟡 MEDIUM RISK" if flags else "🟢 LOW RISK")

    result  = f"*Risk Level*: {risk}\n\n"
    result += "*Placement Issues (based on real data):*\n"
    result += "\n".join(f"  • {f}" for f in flags) if flags else "  ✅ No major issues detected"
    result += "\n\n*Suitability:* "
    if len(flags) >= 3:
        result += "Not recommended for ad placement until issues are resolved."
    elif flags:
        result += "Conditionally suitable — resolve flagged issues first."
    else:
        result += "Suitable for ad placement based on available data."
    if recs:
        result += "\n\n*Recommendations:*\n" + "\n".join(f"  ➡️ {r}" for r in recs)
    return result
