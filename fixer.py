"""
fixer.py — AdApprovalPilot AI
AI-powered fix system. Passes real violation data to Gemini
so fixes are specific to the channel's actual issues, not generic.
"""
import logging
from ai_engine import (
    fix_description,
    fix_name,
    rewrite_post,
)

logger = logging.getLogger(__name__)


def is_compliant_response(text: str) -> bool:
    """Check if AdApprovalPilot AI says the content is already compliant."""
    return bool(text) and text.strip().upper().startswith("COMPLIANT")


def fix_channel_description(
    name: str,
    username: str,
    current_description: str,
    entity_type: str,
    niche: str = "",
    violations: dict = None,
) -> dict:
    """
    Generate AI fix for description.
    Passes violations so Gemini fixes the EXACT issues found.
    Returns {"compliant": bool, "result": str}
    """
    result = fix_description(
        name=name,
        username=username,
        current_description=current_description,
        entity_type=entity_type,
        niche=niche,
        violations=violations or {},
    )
    if is_compliant_response(result):
        return {
            "compliant": True,
            "result": "✅ *Description is already compliant.* No changes required.",
        }
    return {"compliant": False, "result": result}


def fix_channel_name(
    current_name: str,
    username: str,
    entity_type: str,
    issues: list,
) -> dict:
    """
    Generate AI name suggestions based on detected issues.
    Returns {"compliant": bool, "result": str}
    """
    # Handle both tuple format (key, desc, penalty) and plain string
    issue_descriptions = []
    for i in issues:
        if isinstance(i, tuple):
            issue_descriptions.append(i[1])
        else:
            issue_descriptions.append(str(i))

    result = fix_name(current_name, username, entity_type, issue_descriptions)
    if is_compliant_response(result):
        return {
            "compliant": True,
            "result": "✅ *Channel name is already compliant.* No changes required.",
        }
    return {"compliant": False, "result": result}


def fix_single_post(
    post_text: str,
    channel_name: str,
    violation_categories: list,
) -> dict:
    """
    Rewrite a single post using AdApprovalPilot AI.
    Returns {"compliant": bool, "result": str}
    """
    result = rewrite_post(post_text, channel_name, violation_categories)
    if is_compliant_response(result):
        return {
            "compliant": True,
            "result": "✅ This post is already compliant. No changes required.",
        }
    return {"compliant": False, "result": result}


def fix_all_posts(
    posts: list,
    channel_name: str,
    violations_map: dict,
) -> list:
    """
    Rewrite a list of flagged posts.
    violations_map: {post_index: [categories]}
    Returns list of {"original": str, "fixed": str, "compliant": bool}
    """
    results = []
    for i, post in enumerate(posts):
        cats = violations_map.get(i, [])
        fix  = fix_single_post(post, channel_name, cats)
        results.append({
            "original":  post,
            "fixed":     fix["result"],
            "compliant": fix["compliant"],
        })
    return results
