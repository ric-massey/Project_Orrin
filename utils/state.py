from utils.json_utils import load_json
from paths import MODE_FILE

def get_current_mode(default="contemplative"):
    """
    Loads the current operational mode Orrin is in.
    Defaults to 'contemplative' if no mode is set.
    """
    try:
        data = load_json(MODE_FILE, default_type=dict)
        return data.get("mode", default)
    except Exception as e:
        # Optional: Log this if you have a logging system in place
        return default