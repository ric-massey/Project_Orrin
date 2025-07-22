# imports
import json
from cognition.reflection.meta_reflect import meta_reflect
from memory.working_memory import update_working_memory
from utils.json_utils import (
    save_json,
    extract_json
)
from utils.log import (
    log_error,
    log_private
)
from utils.log_reflection import log_reflection
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from paths import (
    COGN_SCHEDULE_FILE
)

def reflect_on_cognition_schedule():
    """
    Adjust Orrin's cognitive rhythm using statistical meta-reflection and higher-order LLM insight.
    Combines usage/satisfaction scoring with full memory introspection.
    """
    from collections import Counter
    from datetime import datetime, timezone

    try:
        # === Load complete system context ===
        data = load_all_known_json()
        stat_schedule = data.get("cognition_schedule", {})
        history = data.get("cognition_history", [])[-50:]
        prompts = data.get("prompts", {})

        old_schedule = dict(stat_schedule)
        usage_counter = Counter()
        value_accumulator = {}
        protected = {"persistent_drive_loop", "choose_next_cognition"}
        reflection_log = []

        # === Step 1: Meta-reflective statistical tuning ===
        for record in history:
            fn = record.get("function") or record.get("choice")
            score = record.get("satisfaction", 0)
            if fn:
                usage_counter[fn] += 1
                value_accumulator[fn] = value_accumulator.get(fn, 0) + score

        for fn, count in usage_counter.items():
            avg_value = value_accumulator.get(fn, 0) / count if count else 0

            reason = meta_reflect({
                **data,
                "function": fn,
                "recent_use_count": count,
                "average_satisfaction": avg_value
            })

            if fn not in stat_schedule:
                stat_schedule[fn] = 1.0

            if avg_value >= 0.5:
                stat_schedule[fn] = min(stat_schedule[fn] + 0.5, 10)
                reflection_log.append(f"↑ Boosted {fn}: {reason}")
            elif avg_value <= 0.3:
                stat_schedule[fn] = max(stat_schedule[fn] - 0.5, 0.1)
                reflection_log.append(f"↓ Reduced {fn}: {reason}")
            else:
                reflection_log.append(f"→ Unchanged {fn}: {reason}")

        # === Step 2: Optional LLM refinement ===
        prompt_template = prompts.get("reflect_on_cognition_rhythm", "")
        if prompt_template:
            recent_entries = "\n".join(
                f"- {h['choice']} on {h['timestamp'].split('T')[0]}: {h.get('reason', '')}"
                for h in history
            )

            context = {
                **data,
                "recent_cognition": history,
                "recent_summary": recent_entries,
                "instructions": (
                    f"{prompt_template}\n\n"
                    f"Here is my current cognition schedule:\n{json.dumps(stat_schedule, indent=2)}\n\n"
                    f"Here are recent cognition choices:\n{recent_entries}\n\n"
                    "If I wish to make any changes, respond ONLY with JSON like:\n"
                    "{ \"dream\": 8, \"reflect_on_self_beliefs\": 4 }\n"
                    "If no changes are needed, respond with: {}\n"
                )
            }

            response = generate_response_from_context(context)
            changes = extract_json(response)

            if isinstance(changes, dict) and changes:
                for k, v in changes.items():
                    if k not in protected:
                        stat_schedule[k] = v
                log_private(f"Orrin revised cognition schedule via LLM:\n{json.dumps(changes, indent=2)}")
            else:
                log_private("Orrin reflected on cognition schedule via LLM: no changes suggested.")

        # === Step 3: Save and log ===
        save_json(COGN_SCHEDULE_FILE, stat_schedule)
        log_private(f"Orrin updated cognition schedule based on usage + insight.\nChanges:\n" +
                    "\n".join(reflection_log))
        log_reflection(f"Self-belief reflection: {' '.join(reflection_log).strip()}")

    except Exception as e:
        log_error(f"reflect_on_cognition_schedule ERROR: {e}")
        update_working_memory("⚠️ Cognition schedule reflection failed.")

    diff = {
        k: (old_schedule.get(k), stat_schedule[k])
        for k in set(old_schedule) | set(stat_schedule)
        if old_schedule.get(k) != stat_schedule.get(k)
    }
    if diff:
        log_private(f"Schedule diff after reflection:\n{json.dumps(diff, indent=2)}")
        update_working_memory("Cognition schedule updated.")
    else:
        update_working_memory("No changes to cognition schedule after reflection.")