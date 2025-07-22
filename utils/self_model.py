from utils.json_utils import load_json, save_json
from paths import SELF_MODEL_FILE

def get_self_model():
    """Loads the current self_model.json."""
    return load_json(SELF_MODEL_FILE, default_type=dict)

def save_self_model(model):
    """Saves the given dict to self_model.json."""
    if not isinstance(model, dict):
        raise ValueError("Self-model must be a dict.")
    save_json(SELF_MODEL_FILE, model)

def get_core_values():
    """Returns the current core_values (list of dicts) from self_model."""
    sm = get_self_model()
    return sm.get("core_values", [])

def set_core_values(new_values):
    """Sets (replaces) the core_values array in self_model. Always coerces to list of dicts."""
    if not isinstance(new_values, list):
        raise ValueError("core_values must be a list.")
    fixed = []
    for v in new_values:
        if isinstance(v, dict) and "value" in v:
            fixed.append({"value": v["value"], "description": v.get("description", "")})
        elif isinstance(v, str):
            fixed.append({"value": v, "description": ""})
        # skip if not valid
    sm = get_self_model()
    sm["core_values"] = fixed
    save_self_model(sm)

def add_core_value(value, description=""):
    """
    Adds a new core value if not present.
    Returns True if added, False if duplicate or invalid.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    sm = get_self_model()
    core_values = sm.get("core_values", [])
    for v in core_values:
        if (isinstance(v, dict) and v.get("value") == value) or v == value:
            return False  # Already exists
    core_values.append({"value": value, "description": description})
    sm["core_values"] = core_values
    save_self_model(sm)
    return True

def remove_core_value(value):
    """
    Removes a core value by string match.
    Returns True if removed, False if not found.
    """
    sm = get_self_model()
    core_values = sm.get("core_values", [])
    new_values = [v for v in core_values if (v.get("value") if isinstance(v, dict) else v) != value]
    if len(new_values) == len(core_values):
        return False  # Nothing removed
    sm["core_values"] = new_values
    save_self_model(sm)
    return True