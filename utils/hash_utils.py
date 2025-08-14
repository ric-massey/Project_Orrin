import hashlib
import json
from typing import Any, Dict
from utils.log import log_model_issue

def hash_context(context: Dict[str, Any]) -> str:
    """
    Creates a stable MD5 hash of the given context dictionary.
    Non-serializable values are coerced to strings.
    """
    try:
        context_str = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.md5(context_str.encode("utf-8")).hexdigest()
    except Exception as e:
        log_model_issue(f"[hash_context] Failed to hash context: {e}")
        return "invalid"