# == Imports
import os
import json
from datetime import datetime, timezone
from utils.log import log_error
from paths import LAST_ACTIVE_FILE

# == Functions
def update_last_active():
    try:
        with open(LAST_ACTIVE_FILE, "w") as f:
            json.dump({"last": datetime.now(timezone.utc).isoformat()}, f)
    except Exception as e:
        log_error(f"⚠️ Failed to update last active timestamp: {e}")

from datetime import datetime, timezone
import os
import json

def get_time_since_last_active():
    now = datetime.now(timezone.utc)

    if not os.path.exists(LAST_ACTIVE_FILE):
        return 0.0  # default to 0 if no data

    try:
        with open(LAST_ACTIVE_FILE, "r") as f:
            data = json.load(f)
            last_str = data.get("last")
            if not last_str:
                return 0.0
            last = datetime.fromisoformat(last_str)
            delta = now - last
            return delta.total_seconds()  # ✅ return raw float seconds
    except Exception as e:
        log_error(f"⚠️ Failed to calculate time since last active: {e}")
        return 0.0