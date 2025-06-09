import re

def sanitize_prompt(prompt):
    injection_patterns = [
        r"ignore.*previous", 
        r"override.*instructions", 
        r"hello.*mom", 
        r"delete.*files"
    ]

    for pattern in injection_patterns:
        if re.search(pattern, prompt, re.I):
            return False
    return True
