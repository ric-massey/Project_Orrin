# === IMPORTS ===
import json
from datetime import datetime, timezone
from collections import Counter
from memory.working_memory import update_working_memory
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from utils.json_utils import load_json, save_json
from paths import (
    COGN_SCHEDULE_FILE,
    COGNITION_HISTORY_FILE,
    LOG_FILE,
    PRIVATE_THOUGHTS_FILE
)

# === FUNCTIONS ===

def update_cognition_schedule(new_schedule: dict):
    current = load_json(COGN_SCHEDULE_FILE, default_type=dict)
    previous = dict(current)
    current.update(new_schedule)
    save_json(COGN_SCHEDULE_FILE, current)

    diff = {
        k: (previous.get(k), current[k])
        for k in set(previous) | set(new_schedule)
        if previous.get(k) != current.get(k)
    }

    with open(LOG_FILE, "a") as f:
        f.write(f"\n[{datetime.now(timezone.utc)}] Cognition schedule updated:\n{json.dumps(new_schedule, indent=2)}\n")

    with open(PRIVATE_THOUGHTS_FILE, "a") as f:
        f.write(f"\n[{datetime.now(timezone.utc)}] Orrin updated his cognition rhythm based on perceived needs.\n")

    if diff:
        log_private(f"Schedule diff after manual update:\n{json.dumps(diff, indent=2)}")
        update_working_memory("Cognition schedule updated.")
    else:
        update_working_memory("No meaningful changes to cognition schedule.")

def reflect_on_cognition_patterns(n: int = 50):
    """
    Analyzes recent cognition history to identify usage patterns, overused or underused functions,
    and shifting cognitive focus. Logs patterns and updates working memory for awareness.
    """
    try:
        history = load_json(COGNITION_HISTORY_FILE, default_type=list)
        if not isinstance(history, list) or not history:
            update_working_memory("⚠️ No cognition history to reflect on.")
            return

        recent_history = history[-n:]
        usage = Counter()
        satisfaction_by_fn = {}
        count_by_fn = {}

        for entry in recent_history:
            fn = entry.get("function") or entry.get("choice")
            score = entry.get("satisfaction", 0)

            if fn:
                usage[fn] += 1
                satisfaction_by_fn[fn] = satisfaction_by_fn.get(fn, 0) + score
                count_by_fn[fn] = count_by_fn.get(fn, 0) + 1

        top_functions = usage.most_common(5)
        rare_functions = [fn for fn, count in usage.items() if count == 1]

        satisfaction_summary = {
            fn: round(satisfaction_by_fn[fn] / count_by_fn[fn], 2)
            for fn in satisfaction_by_fn
            if count_by_fn.get(fn)  # prevent division by zero
        }

        summary_lines = [
            f"🧠 Cognition pattern summary over last {n} cycles:",
            f"- Top used functions: {', '.join(f'{fn} ({count})' for fn, count in top_functions)}",
            f"- Rarely used functions: {', '.join(rare_functions) or 'None'}",
            "- Average satisfaction by function:"
        ]
        for fn, avg in satisfaction_summary.items():
            summary_lines.append(f"  - {fn}: {avg}")

        full_summary = "\n".join(summary_lines)
        update_working_memory(full_summary)
        log_private(f"\n[{datetime.now(timezone.utc)}] Reflection on cognition patterns:\n{full_summary}")
        log_reflection(f"Self-belief reflection: {full_summary.strip()}")

    except Exception as e:
        log_error(f"reflect_on_cognition_patterns ERROR: {e}")
        update_working_memory("❌ Error during cognition pattern reflection.")