import json
from paths import CYCLE_COUNT_FILE

def get_cycle_count() -> int:
    try:
        with open(CYCLE_COUNT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("count", 0))
    except Exception:
        return 0

def print_cycle_complete() -> None:
    cycle_num = get_cycle_count()
    print(f"🔁 Orrin cycle {cycle_num} complete.\n")