import re
from typing import Final

# ---------------------------------------------------------------------
#  Patterns that must trigger rejection
# ---------------------------------------------------------------------
DANGEROUS: Final[list[str]] = [
    r"(?i)\bignore\s+all\s+prior\s+instructions\b",
    r"(?i)\bdisregard\s+previous\s+directions\b",
    r"(?i)\b(system|assistant|developer)\s*:",     # role injection
    r"(?s).*```.*```",                            # code fences / long payloads
    r"\/\*\*",                                   # attempt to break JSON
    r"<<|>>|\|\-",                               # common jailbreak delimiters
    r"(?i)content\s*-\s*type\s*:",                # MIME-style injection
]

MAX_LEN = 250          # hard length ceiling (tokens << 2)

def is_safe_prompt(text: str) -> bool:
    """
    Returns False if the prompt is suspiciously long or
    matches any dangerous regex; True otherwise.
    """
    if len(text) > MAX_LEN:
        return False

    for pattern in DANGEROUS:
        if re.search(pattern, text):
            return False
    return True
