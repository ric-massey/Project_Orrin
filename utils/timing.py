from datetime import datetime, timezone
import json
from utils.log import log_error
from paths import LAST_ACTIVE_FILE  # pathlib.Path

# === Update Last Active ===
def update_last_active():
    try:
        LAST_ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LAST_ACTIVE_FILE.open("w", encoding="utf-8", newline="\n") as f:
            json.dump({"last": datetime.now(timezone.utc).isoformat()}, f)
    except Exception as e:
        log_error(f"⚠️ Failed to update last active timestamp: {e}")

# === Get Time Since Last Active (seconds, float) ===
def get_time_since_last_active() -> float:
    now = datetime.now(timezone.utc)

    if not LAST_ACTIVE_FILE.exists():
        return 0.0

    try:
        with LAST_ACTIVE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        last_str = data.get("last")
        if not last_str or not isinstance(last_str, str):
            return 0.0

        # tolerate Z-suffix
        last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
        # ensure tz-aware
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        delta = now - last_dt
        return max(0.0, float(delta.total_seconds()))
    except Exception as e:
        log_error(f"⚠️ Failed to calculate time since last active: {e}")
        return 0.0