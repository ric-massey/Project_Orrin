from datetime import datetime, timezone
from paths import (
    ERROR_FILE, MODEL_FAILURE, ACTIVITY_LOG, 
    PRIVATE_THOUGHTS_FILE
)

def log_error(content):
    with open(ERROR_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] {content}\n")

def log_model_issue(message):
    with open(MODEL_FAILURE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")

def log_activity(message):
    with open(ACTIVITY_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")

def log_private(message):
    with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")

