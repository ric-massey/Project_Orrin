from datetime import datetime, timezone
from utils.log import log_private

def log_reward_spike(signal_type="dopamine", strength=1.0, tags=None):
    timestamp = datetime.now(timezone.utc).isoformat()
    tags = tags or []
    log_entry = (
        f"[{timestamp}] Reward spike — Signal: {signal_type}, Strength: {strength:.2f}, Tags: {tags}"
    )
    log_private(log_entry)