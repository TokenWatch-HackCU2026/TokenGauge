"""
Heuristic prompt complexity classifier.

Scores every proxy request at call time — no extra LLM call needed.
Returns:
  complexity: int 1–10
  prompt_type: "code" | "creative" | "analysis" | "chat" | "other"
"""

import re
from typing import Any

_CODE = re.compile(
    r"```|def |class |function |import |#include|SELECT |INSERT |CREATE TABLE"
    r"|async |await |console\.|print\(|System\.out|<\?php|\bSQL\b|\bAPI\b",
    re.IGNORECASE,
)
_ANALYSIS = re.compile(
    r"\b(analyz|compar|evaluat|explain|describ|summariz|review|critiqu"
    r"|assess|investigat|diagnos|break.?down|step.?by.?step)\b",
    re.IGNORECASE,
)
_CREATIVE = re.compile(
    r"\b(write a story|write a poem|write an essay|create a|compose|imagine"
    r"|generate a|roleplay|pretend|fictional|narrative)\b",
    re.IGNORECASE,
)


def _extract_text(messages: list[dict[str, Any]]) -> str:
    """Pull all user/human message text out of a messages array."""
    parts: list[str] = []
    for m in messages:
        if m.get("role") not in ("user", "human"):
            continue
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return " ".join(parts)


def classify_prompt(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Classify a list of chat messages.

    Returns {"complexity": int, "prompt_type": str}
    """
    if not messages:
        return {"complexity": 1, "prompt_type": "chat"}

    text = _extract_text(messages)
    word_count = len(text.split())

    # Determine type
    if _CODE.search(text):
        prompt_type = "code"
    elif _ANALYSIS.search(text):
        prompt_type = "analysis"
    elif _CREATIVE.search(text):
        prompt_type = "creative"
    else:
        prompt_type = "chat"

    # Base complexity from word count
    if word_count < 15:
        base = 2
    elif word_count < 50:
        base = 3
    elif word_count < 150:
        base = 5
    elif word_count < 400:
        base = 7
    else:
        base = 9

    # Bump for technically demanding types
    if prompt_type in ("code", "analysis"):
        base = min(10, base + 1)

    return {"complexity": base, "prompt_type": prompt_type}
