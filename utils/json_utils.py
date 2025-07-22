#imports
import re
import os
import json
import fcntl
from utils.log import log_model_issue

# ==Functions


def extract_json(text):
    """
    Extract the first valid JSON object from a string even if surrounded by markdown or extra text.
    Returns a Python dict or 'extract ERROR' if parsing fails.
    """
    try:
        # Try to extract JSON inside ```json ... ``` markdown block
        match = re.search(r"```json\s*({.*?})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try to extract the first balanced JSON object (non-greedy)
        # This pattern attempts to find JSON by balancing braces using a stack approach:
        brace_level = 0
        start_idx = None
        for i, char in enumerate(text):
            if char == '{':
                if brace_level == 0:
                    start_idx = i
                brace_level += 1
            elif char == '}':
                brace_level -= 1
                if brace_level == 0 and start_idx is not None:
                    candidate = text[start_idx:i+1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass  # Not valid JSON, continue searching

        # Final fallback: try direct load (in case the entire text is JSON)
        return json.loads(text)

    except json.JSONDecodeError as e:
        log_model_issue(f"[extract_json] JSON decode error: {e}\nRaw: {text[:300]}")
        return "extract ERROR"
    
def save_json(filepath, data):
    """
    Saves Python data as JSON to the specified file path with file locking.
    """
    try:
        with open(filepath, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
            json.dump(data, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        log_model_issue(f"[save_json] Failed to save {filepath}: {e}")


def load_json(filepath, default_type=dict):
    """
    Loads JSON data from a file, or returns a default empty type if the file is missing, empty, or corrupt.
    """
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return default_type()
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        log_model_issue(f"[load_json] Failed to load {filepath}: {e}")
        return default_type()
    
