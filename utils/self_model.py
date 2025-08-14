from __future__ import annotations
from typing import Any, Dict, List, Tuple, Union
from utils.json_utils import load_json, save_json
from paths import SELF_MODEL_FILE

SelfModel = Dict[str, Any]

_EXPECTED_LIST_KEYS: List[str] = ["core_values", "traits", "known_roles", "recent_focus"]

def _coerce_list(val: Any) -> List[Any]:
    return val if isinstance(val, list) else []

def ensure_self_model_integrity(
    model: Any,
    *,
    with_flag: bool = False,
) -> Union[SelfModel, Tuple[SelfModel, bool]]:
    """
    Ensure expected fields exist and are well-typed. Does not write to disk.

    Returns:
      - dict (default), or
      - (dict, updated_flag) if with_flag=True

    Note: Defaulting to a dict avoids accidental tuple propagation to callers
    that immediately do `self_model.get(...)`.
    """
    updated = False
    sm: SelfModel = model if isinstance(model, dict) else {}
    if not isinstance(model, dict):
        updated = True

    # core_directive → dict{statement:str}
    cd = sm.get("core_directive")
    if isinstance(cd, str):
        text = cd.strip()
        sm["core_directive"] = {
            "statement": text if text and text.lower() not in ("not found", "none")
            else "Define a purpose and seek growth"
        }
        updated = True
    elif isinstance(cd, dict):
        if not cd.get("statement"):
            cd["statement"] = "Define a purpose and seek growth"
            updated = True
        sm["core_directive"] = cd
    else:
        sm["core_directive"] = {"statement": "Define a purpose and seek growth"}
        updated = True

    # identity -> non-empty string
    ident = sm.get("identity")
    if not isinstance(ident, str) or not ident.strip():
        sm["identity"] = "Evolving reflective AI"
        updated = True

    # Normalize list-typed fields
    # core_values → List[{"value": str, "description": str}]
    if "core_values" not in sm or not isinstance(sm.get("core_values"), list):
        sm["core_values"] = []
        updated = True
    else:
        normalized_cv: List[Dict[str, str]] = []
        for v in _coerce_list(sm.get("core_values")):
            if isinstance(v, dict) and isinstance(v.get("value"), str):
                normalized_cv.append({
                    "value": v["value"].strip(),
                    "description": (v.get("description") or "").strip(),
                })
            elif isinstance(v, str) and v.strip():
                normalized_cv.append({"value": v.strip(), "description": ""})
            # silently drop malformed entries
        if normalized_cv != sm.get("core_values"):
            sm["core_values"] = normalized_cv
            updated = True

    # traits / known_roles / recent_focus → List[str]
    for key in ("traits", "known_roles", "recent_focus"):
        current = sm.get(key)
        if not isinstance(current, list):
            sm[key] = []
            updated = True
        else:
            norm: List[str] = []
            for item in current:
                if isinstance(item, str):
                    s = item.strip()
                    if s:
                        norm.append(s)
            if norm != current:
                sm[key] = norm
                updated = True

    return (sm, updated) if with_flag else sm

def get_self_model() -> SelfModel:
    """Load, repair if needed, and persist only when changed. Always returns a dict."""
    raw = load_json(SELF_MODEL_FILE, default_type=dict)
    sm, updated = ensure_self_model_integrity(raw, with_flag=True)  # returns (dict, bool)
    if updated:
        save_json(SELF_MODEL_FILE, sm)
    return sm

def save_self_model(model: Any) -> None:
    """Repair then save once. Accepts anything coercible to dict."""
    sm, _ = ensure_self_model_integrity(model, with_flag=True)
    save_json(SELF_MODEL_FILE, sm)

def get_core_values() -> List[Dict[str, str]]:
    sm = get_self_model()
    vals = sm.get("core_values", [])
    return vals if isinstance(vals, list) else []

def set_core_values(new_values: Any) -> None:
    if not isinstance(new_values, list):
        raise ValueError("core_values must be a list.")
    fixed: List[Dict[str, str]] = []
    for v in new_values:
        if isinstance(v, dict) and "value" in v and isinstance(v["value"], str):
            fixed.append({"value": v["value"].strip(), "description": (v.get("description") or "").strip()})
        elif isinstance(v, str) and v.strip():
            fixed.append({"value": v.strip(), "description": ""})
    sm = get_self_model()
    if sm.get("core_values") != fixed:
        sm["core_values"] = fixed
        save_self_model(sm)

def add_core_value(value: str, description: str = "") -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    sm = get_self_model()
    cv = sm.get("core_values", [])
    val = value.strip()
    for v in cv:
        if (isinstance(v, dict) and v.get("value") == val) or v == val:
            return False
    cv.append({"value": val, "description": description.strip()})
    sm["core_values"] = cv
    save_self_model(sm)
    return True

def remove_core_value(value: str) -> bool:
    sm = get_self_model()
    cv = sm.get("core_values", [])
    target = value.strip() if isinstance(value, str) else str(value)
    new_vals = [v for v in cv if (v.get("value") if isinstance(v, dict) else v) != target]
    if len(new_vals) == len(cv):
        return False
    sm["core_values"] = new_vals
    save_self_model(sm)
    return True
