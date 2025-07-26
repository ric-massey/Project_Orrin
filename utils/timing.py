from datetime import datetime, timezone
import json
from utils.log import log_error
from paths import LAST_ACTIVE_FILE  

# === Update Last Active ===
def update_last_active():
    try:
        with LAST_ACTIVE_FILE.open("w", encoding="utf-8", newline="\n") as f:
            json.dump({"last": datetime.now(timezone.utc).isoformat()}, f)
    except Exception as e:
        log_error(f"⚠️ Failed to update last active timestamp: {e}")

# === Get Time Since Last Active ===
def get_time_since_last_active():
    now = datetime.now(timezone.utc)

    if not LAST_ACTIVE_FILE.exists():
        return 0.0  # default to 0 if no data

    try:
        with LAST_ACTIVE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            last_str = data.get("last")
            if not last_str:
                return 0.0
            last = datetime.fromisoformat(last_str)
            delta = now - last
            return delta.total_seconds()
    except Exception as e:
        log_error(f"⚠️ Failed to calculate time since last active: {e}")
        return 0.0