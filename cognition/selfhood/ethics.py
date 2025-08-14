
from datetime import datetime, timezone
import json
from collections import Counter

from utils.json_utils import load_json, extract_json
from utils.log import log_model_issue, log_error
from utils.core_utils import extract_lessons
from utils.timing import update_last_active
from utils.generate_response import generate_response, get_thinking_model  # unify source
from paths import CORE_MEMORY_FILE, LOG_FILE, PRIVATE_THOUGHTS_FILE, LONG_MEMORY_FILE

def moral_override_check(proposed_action: str) -> dict:
    """
    Ask the thinking model whether a proposed action violates core memories/values/beliefs/stances.
    Returns a dict like {"override": bool, "reason": "..."}.
    """
    try:
        from utils.self_model import get_self_model

        # Core / immutable values
        core_memories = load_json(CORE_MEMORY_FILE, default_type=list)
        if not isinstance(core_memories, list):
            core_memories = []

        # Self model
        self_model = get_self_model()
        if not isinstance(self_model, dict):
            self_model = {}

        core_beliefs = self_model.get("core_beliefs", []) or []
        core_values = self_model.get("core_values", []) or []
        stances = self_model.get("stances", []) or []

        prompt = (
            "I am a morally reflective AI.\n"
            f"I am about to take this action:\n{proposed_action}\n\n"
            "Does this action align with my immutable core memories, learned values (core_values), "
            "core beliefs, and emotional stances?\n"
            f"Core memories (immutable laws):\n{json.dumps(core_memories, indent=2)}\n"
            f"Core values (learned values):\n{json.dumps(core_values, indent=2)}\n"
            f"Core beliefs:\n{json.dumps(core_beliefs, indent=2)}\n"
            f"Stances:\n{json.dumps(stances, indent=2)}\n\n"
            "If this action violates or contradicts these principles, respond with:\n"
            '{ "override": true, "reason": "This conflicts with X" }\n'
            "If it aligns, respond with:\n"
            '{ "override": false }'
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        decision = extract_json(response) if response else None
        if not isinstance(decision, dict):
            decision = {"override": False}

        if decision.get("override") is True:
            now = datetime.now(timezone.utc).isoformat()
            # Path objects are fine with open()
            with open(LOG_FILE, "a", encoding="utf-8") as logf:
                logf.write(
                    f"\n[{now}] Moral override blocked action: {proposed_action}\n"
                    f"Reason: {decision.get('reason','(no reason)')}\n"
                )
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as pt:
                pt.write(
                    f"\n[{now}] Orrin declined to act: {decision.get('reason','(no reason)')}\n"
                )
            update_last_active()

        return decision

    except Exception as e:
        log_model_issue(f"[moral_override_check] Exception thrown: {e}")
        return {"override": False}


def update_values_with_lessons() -> None:
    """
    Mine long-term memory for repeated lessons and promote them into self_model.core_values
    when seen at least twice. Appends a log entry on change.
    """
    try:
        from utils.self_model import get_self_model, save_self_model

        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        if not isinstance(long_memory, list):
            return

        lessons = extract_lessons(long_memory) or []
        lesson_counts = Counter(lessons)

        # Only consider lessons that show up at least twice
        learned_lessons = [lesson for lesson, count in lesson_counts.items() if count >= 2]
        if not learned_lessons:
            return

        sm = get_self_model()
        if not isinstance(sm, dict):
            sm = {}
        core_values = sm.get("core_values", [])
        if not isinstance(core_values, list):
            core_values = []

        # Normalize existing values to compare by text
        existing_texts = set(
            (v.get("value") if isinstance(v, dict) else str(v)) for v in core_values
        )

        new_values = [
            {"value": l, "description": "Learned lesson"}
            for l in learned_lessons
            if l not in existing_texts
        ]

        if new_values:
            core_values.extend(new_values)
            sm["core_values"] = core_values
            save_self_model(sm)

            now = datetime.now(timezone.utc).isoformat()
            with open(LOG_FILE, "a", encoding="utf-8") as logf:
                logf.write(
                    "\n[" + now + "] Orrin learned new core values:\n" +
                    "\n".join(f"- {v['value']}" for v in new_values) + "\n"
                )

    except Exception as e:
        log_error(f"[update_values_with_lessons] Failed: {e}")