from utils.json_utils import save_json, load_json
from paths import CYCLE_COUNT_FILE

def manage_cycle_count(context):
    """
    Increments and persists the cognitive cycle count.
    - Loads from CYCLE_COUNT_FILE (ALWAYS), increments, saves, updates context.
    Returns the updated context and the new cycle_count dict.
    """
    # Always load from file (persistent)
    cycle_count = load_json(CYCLE_COUNT_FILE, default_type=dict)
    if "count" not in cycle_count:
        cycle_count["count"] = 0
    cycle_count["count"] += 1

    # Save and update context
    save_json(CYCLE_COUNT_FILE, cycle_count)
    context["cycle_count"] = cycle_count
    return context, cycle_count