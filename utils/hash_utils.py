import hashlib
import json
from utils.log import log_model_issue

def hash_context(context: dict) -> str:
    try:
        context_str = json.dumps(context, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(context_str.encode("utf-8")).hexdigest()
    except Exception as e:
        log_model_issue(f"[hash_context] Failed to hash context: {e}")
        return "invalid"