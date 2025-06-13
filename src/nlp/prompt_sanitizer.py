"""
Rejects prompts likely to be prompt-injection or
malformed payloads before they reach OpenAI.
"""

import re
from typing import Final

MAX_LEN = 250          # keep ≤250 chars (~100 tokens)

# --------- 1. Compile dangerous patterns once ------------------------
_PATTERNS: Final[list[re.Pattern]] = [
    # role / instruction hijacking
    re.compile(r"\b(?:ignore|disregard|override)[^.\n]*?(?:system|previous|prior|developer|assistant)\b", re.I),
    # explicit role field in JSON
    re.compile(r'"\s*role"\s*:\s*"', re.I),
    # opening of code block or long delimiters
    re.compile(r"(?:```|~~~|<<|>>|\|\-)", re.S),
    # attempts to break JSON via comment tokens
    re.compile(r"/\*\*|//", re.S),
    # MIME / header injection
    re.compile(r"content\s*-\s*type\s*:", re.I),
]

# --------- 2. Control-character detection ---------------------------
_CTRL_CHARS = re.compile(r"[\x00-\x1F\x7F]")

def is_safe_prompt(text: str) -> bool:
    """
    Returns True if prompt looks safe, False otherwise.
    Enforces length limit, rejects control chars,
    and scans for known jailbreak patterns.
    """
    if len(text) > MAX_LEN:
        return False
    if _CTRL_CHARS.search(text):
        return False

    for pat in _PATTERNS:
        if pat.search(text):
            return False
    return True
