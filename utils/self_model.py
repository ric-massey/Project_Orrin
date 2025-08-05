from utils.json_utils import load_json, save_json
from paths import SELF_MODEL_FILE


def ensure_self_model_integrity(model: dict) -> dict:
    """Ensure all expected fields exist and are valid; patch if needed. Save only if updated."""
    updated = False
    if "core_directive" not in model or not model["core_directive"] or model["core_directive"] in ("Not found", "none", ""):
        model["core_directive"] = "Define a purpose and seek growth"
        updated = True
    if "core_values" not in model or not isinstance(model["core_values"], list):
        model["core_values"] = []
        updated = True
    if "traits" not in model or not isinstance(model["traits"], list):
        model["traits"] = []
        updated = True
    if "identity" not in model or not model["identity"]:
        model["identity"] = "Evolving reflective AI"
        updated = True
    if "known_roles" not in model or not isinstance(model["known_roles"], list):
        model["known_roles"] = []
        updated = True
    if "recent_focus" not in model or not isinstance(model["recent_focus"], list):
        model["recent_focus"] = []
        updated = True
    if updated:
        save_json(SELF_MODEL_FILE, model)
    return model

def get_self_model() -> dict:
    """Loads the current self_model.json and ensures integrity before returning."""
    sm = load_json(SELF_MODEL_FILE, default_type=dict)
    sm = ensure_self_model_integrity(sm)
    return sm

def save_self_model(model: dict) -> None:
    """Ensures integrity and saves the given dict to self_model.json."""
    if not isinstance(model, dict):
        raise ValueError("Self-model must be a dict.")
    model = ensure_self_model_integrity(model)
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