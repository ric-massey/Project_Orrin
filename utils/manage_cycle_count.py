from utils.json_utils import save_json
from paths import CYCLE_COUNT_FILE

def manage_cycle_count(context):
    """
    Increments and persists the cognitive cycle count.
    - Adds 1 to cycle_count["count"]
    - Updates context["cycle_count"]
    - Saves to CYCLE_COUNT_FILE
    Returns the updated context and the new cycle_count dict.
    """
    # Get or initialize cycle count from context
    cycle_count = context.get("cycle_count", {"count": 0})
    cycle_count["count"] += 1

    # Save and update context
    save_json(CYCLE_COUNT_FILE, cycle_count)
    context["cycle_count"] = cycle_count
    return context, cycle_count