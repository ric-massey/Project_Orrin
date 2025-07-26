from datetime import datetime, timezone
import json
from collections import Counter
from utils.json_utils import (
    load_json,
    extract_json, 
)
from utils.log import log_model_issue, log_error
from utils.core_utils import extract_lessons
from utils.timing import update_last_active
from paths import (
    LOG_FILE, PRIVATE_THOUGHTS_FILE, CORE_MEMORY_FILE, LONG_MEMORY_FILE
)
from utils.core_utils import get_thinking_model
from utils.generate_response import generate_response

def moral_override_check(proposed_action):
    try:
        from utils.self_model import get_self_model

        # Load core/immutable values
        core_memories = load_json(CORE_MEMORY_FILE, default_type=list)
        if not isinstance(core_memories, list):
            core_memories = []

        # Load self model for all values/beliefs/etc
        self_model = get_self_model()
        if not isinstance(self_model, dict):
            self_model = {}

        core_beliefs = self_model.get("core_beliefs", [])
        core_values = self_model.get("core_values", [])    # This replaces VALUES
        stances = self_model.get("stances", [])

        # Compose value set
        all_values = {
            "core_memories": core_memories,
            "core_values": core_values,
            "core_beliefs": core_beliefs,
            "stances": stances
        }

        prompt = (
            f"I am a morally reflective AI.\n"
            f"I am about to take this action:\n{proposed_action}\n\n"
            "Does this action align with my immutable core memories, learned values (core_values), core beliefs, and emotional stances?\n"
            f"Core memories (immutable laws):\n{json.dumps(core_memories, indent=2)}\n"
            f"Core values (learned values):\n{json.dumps(core_values, indent=2)}\n"
            f"Core beliefs:\n{json.dumps(core_beliefs, indent=2)}\n"
            f"Stances:\n{json.dumps(stances, indent=2)}\n\n"
            "If this action violates or contradicts these principles, respond with:\n"
            "{ \"override\": true, \"reason\": \"This conflicts with X\" }\n"
            "If it aligns, respond with:\n"
            "{ \"override\": false }"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        decision = extract_json(response) if response else {"override": False}

        if isinstance(decision, dict) and decision.get("override") is True:
            with open(LOG_FILE, "a") as log:
                log.write(f"\n[{datetime.now(timezone.utc)}] Moral override blocked action: {proposed_action}\nReason: {decision.get('reason')}\n")
            with open(PRIVATE_THOUGHTS_FILE, "a") as pt:
                pt.write(f"\n[{datetime.now(timezone.utc)}] Orrin declined to act: {decision.get('reason')}\n")
            update_last_active()
        return decision if isinstance(decision, dict) else {"override": False}

    except Exception as e:
        log_model_issue(f"[moral_override_check] Exception thrown: {e}")
    return {"override": False}

def update_values_with_lessons():
    from utils.self_model import get_self_model, save_self_model

    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        return

    lessons = extract_lessons(long_memory)
    lesson_counts = Counter(lessons)

    # Only lessons seen at least twice
    learned_lessons = [lesson for lesson, count in lesson_counts.items() if count >= 2]

    if learned_lessons:
        try:
            sm = get_self_model()
            core_values = sm.get("core_values", [])
            # Only add new lessons if not already present
            new_values = [
                {"value": l, "description": "Learned lesson"} 
                for l in learned_lessons 
                if not any(
                    (v.get("value") if isinstance(v, dict) else v) == l
                    for v in core_values
                )
            ]
            if new_values:
                core_values.extend(new_values)
                sm["core_values"] = core_values
                save_self_model(sm)

                with open(LOG_FILE, "a") as log:
                    log.write(f"\n[{datetime.now(timezone.utc)}] Orrin learned new core values:\n" + "\n".join(f"- {v['value']}" for v in new_values) + "\n")
        except Exception as e:
            log_error(f"[update_values_with_lessons] Failed: {e}")