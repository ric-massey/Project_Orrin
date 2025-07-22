import hashlib
from utils.log import log_model_issue
import json

def hash_context(context: dict) -> str:
    try:
        context_str = json.dumps(context, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()
    except Exception as e:
        log_model_issue(f"[hash_context] Failed to hash context: {e}")
        return "invalid"