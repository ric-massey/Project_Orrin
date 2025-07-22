# === Imports ===
from utils.json_utils import load_json
from paths import EMOTION_MODEL_FILE
from utils.log import log_error  # Optional: helpful for diagnostics

# === Functions ===
def load_emotion_keywords():
    try:
        data = load_json(EMOTION_MODEL_FILE, default_type=dict)
        if not isinstance(data, dict):
            log_error("⚠️ Emotion model was not a dictionary. Returning empty model.")
            return {}
        return data
    except Exception as e:
        log_error(f"⚠️ Failed to load emotion model: {e}")
        return {}