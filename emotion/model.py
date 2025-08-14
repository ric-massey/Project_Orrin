from typing import Dict, List, Any
from utils.json_utils import load_json
from utils.log import log_error
from paths import EMOTION_MODEL_FILE

def load_emotion_keywords() -> Dict[str, List[str]]:
    """Load emotion->keywords map, normalized to {str: [str, ...]}."""
    try:
        raw: Any = load_json(EMOTION_MODEL_FILE, default_type=dict)
        if not isinstance(raw, dict):
            log_error("⚠️ Emotion model was not a dictionary. Returning empty model.")
            return {}

        normalized: Dict[str, List[str]] = {}
        for k, v in raw.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, list):
                # keep only strings, strip whitespace
                keywords = [str(x).strip() for x in v if isinstance(x, str) and x.strip()]
            elif isinstance(v, str):
                keywords = [v.strip()] if v.strip() else []
            else:
                keywords = []
            if keywords:
                normalized[k] = keywords
        return dict(normalized)  # shallow copy
    except Exception as e:
        log_error(f"⚠️ Failed to load emotion model: {e}")
        return {}