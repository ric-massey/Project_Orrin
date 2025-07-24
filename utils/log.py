from datetime import datetime, timezone
from paths import (
    ERROR_FILE, MODEL_FAILURE, ACTIVITY_LOG, 
    PRIVATE_THOUGHTS_FILE
)

def log_error(content):
    with ERROR_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] {content}\n")

def log_model_issue(message):
    with MODEL_FAILURE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")

def log_activity(message):
    with ACTIVITY_LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")

def log_private(message):
    with PRIVATE_THOUGHTS_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")

def read_recent_errors_txt(path, max_lines=5):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-max_lines:] if lines else []
    except Exception as e:
        return [f"⚠️ Failed to read {path}: {e}"]

def read_recent_errors_json(path, max_items=5):
    from utils.json_utils import load_json
    try:
        return load_json(path, default_type=list)[-max_items:]
    except Exception as e:
        return [{"error": f"⚠️ Failed to read {path}: {e}"}]