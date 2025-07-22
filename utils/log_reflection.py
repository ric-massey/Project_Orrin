from datetime import datetime, timezone
from utils.append import append_to_json
from paths import REFLECTION

def log_reflection(message, reflection_type="unspecified"):
    entry = {
        "type": reflection_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": message.strip()
    }
    append_to_json(REFLECTION, entry)