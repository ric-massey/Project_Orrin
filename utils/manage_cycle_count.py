from __future__ import annotations

from typing import Dict, Tuple, Any
from utils.json_utils import save_json, load_json
from paths import CYCLE_COUNT_FILE

def manage_cycle_count(context: Dict[str, Any] | None) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Increments and persists the cognitive cycle count.

    Always loads from CYCLE_COUNT_FILE, increments, saves, and updates context.
    Returns (updated_context, cycle_count_dict).
    """
    # Ensure context is mutable dict
    if not isinstance(context, dict):
        context = {}

    # Load persisted counter; tolerate corruption or wrong types
    raw = load_json(CYCLE_COUNT_FILE, default_type=dict)
    cycle_count: Dict[str, int] = raw if isinstance(raw, dict) else {}
    count_val = cycle_count.get("count", 0)

    # Coerce to int defensively
    try:
        count_int = int(count_val)
        if count_int < 0:
            count_int = 0
    except (TypeError, ValueError):
        count_int = 0

    cycle_count["count"] = count_int + 1

    # Persist and reflect into context
    save_json(CYCLE_COUNT_FILE, cycle_count)
    context["cycle_count"] = cycle_count
    return context, cycle_count