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