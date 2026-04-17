"""
fixer.py
AI-powered fix system for posts, descriptions, and names.
Integrates with ai_engine.py for unique, context-aware fixes.
"""
import logging
from ai_engine import (
    fix_description,
    fix_name,
    rewrite_post,
)

logger = logging.getLogger(__name__)

COMPLIANT_SIGNAL = "COMPLIANT:"


def is_compliant_response(text: str) -> bool:
    """Check if AI says the content is already compliant."""
    return text.strip().upper().startswith("COMPLIANT")


def fix_channel_description(
    name: str,
    username: str,
    current_description: str,
    entity_type: str,
    niche: str = "",
) -> dict:
    """
    Generate AI fix for description.
    Returns {"compliant": bool, "result": str}
    """
    result = fix_description(name, username, current_description, entity_type, niche)
    if is_compliant_response(result):
        return {"compliant": True, "result": "✅ *Description is already compliant.* No changes required."}
    return {"compliant": False, "result": result}


def fix_channel_name(
    current_name: str,
    username: str,
    entity_type: str,
    issues: list,
) -> dict:
    """
    Generate AI name suggestions.
    Returns {"compliant": bool, "result": str}
    """
    issue_descriptions = [desc for _, desc, _ in issues]
    result = fix_name(current_name, username, entity_type, issue_descriptions)
    if is_compliant_response(result):
        return {"compliant": True, "result": "✅ *Channel name is already compliant.* No changes required."}
    return {"compliant": False, "result": result}


def fix_single_post(
    post_text: str,
    channel_name: str,
    violation_categories: list,
) -> dict:
    """
    Rewrite a single post using AI.
    Returns {"compliant": bool, "result": str}
    """
    result = rewrite_post(post_text, channel_name, violation_categories)
    if is_compliant_response(result):
        return {"compliant": True, "result": "✅ This post is already compliant. No changes required."}
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
