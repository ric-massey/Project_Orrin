import re
import os
import json
import platform
from pathlib import Path
from utils.log import log_model_issue

# Optional: Use fcntl only on Unix systems
if platform.system() != "Windows":
    import fcntl


def extract_json(text):
    try:
        match = re.search(r"```json\s*({.*?})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

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
                        pass
        return json.loads(text)
    except json.JSONDecodeError as e:
        log_model_issue(f"[extract_json] JSON decode error: {e}\nRaw: {text[:300]}")
        return "extract ERROR"


def save_json(filepath, data):
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as f:
            if platform.system() != "Windows":
                fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
            if platform.system() != "Windows":
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        log_model_issue(f"[save_json] Failed to save {filepath}: {e}")


def load_json(filepath, default_type=dict):
    try:
        path = Path(filepath)
        if not path.exists() or path.stat().st_size == 0:
            return default_type()
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_model_issue(f"[load_json] Failed to load {filepath}: {e}")
        return default_type()