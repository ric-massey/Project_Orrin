import json
import json
import time

def get_cycle_count():
    try:
        with open("cycle_count.json", "r") as f:
            data = json.load(f)
        return data.get("count", 0)
    except Exception:
        return 0

def print_cycle_complete():
    cycle_num = get_cycle_count()
    print(f"🔁 Orrin cycle {cycle_num} complete.\n")