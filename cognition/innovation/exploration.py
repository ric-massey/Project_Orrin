# === Standard Library ===
import os
import json
from datetime import datetime, timezone

# === Internal Utility Imports ===
from utils.core_utils import (
    extract_questions,
    rate_satisfaction 
)
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import (
    extract_json, load_json, save_json
)
from memory.working_memory import update_working_memory
from utils.log import log_error

# === File Constants ===
from paths import (
    CURIOUS_GEORGE,
    CORE_MEMORY_FILE,
    WORLD_MODEL,
    CASUAL_RULES,
    PRIVATE_THOUGHTS_FILE
)

# == Functions ==
def curiosity_loop():
    curiosity = load_json(CURIOUS_GEORGE, default_type=list)
    if not isinstance(curiosity, list):
        log_error("⚠️ CURIOUS_GEORGE is not a list. Resetting to empty list.")
        curiosity = []

    if not curiosity:
        prompt = (
            "What am I currently curious about? What questions do I have about myself, the user, or the world?"
        )
        new_qs = generate_response(prompt, config={"model": get_thinking_model()})
        for q in extract_questions(new_qs):
            curiosity.append({
                "question": q,
                "status": "open",
                "attempts": 0,
                "satisfaction": 0.0,
                "last_thought": datetime.now(timezone.utc).isoformat()
            })
        save_json(CURIOUS_GEORGE, curiosity)

    open_qs = [q for q in curiosity if q.get("status") == "open"]
    if not open_qs:
        return

    top_q = sorted(open_qs, key=lambda q: -q.get("satisfaction", 0))[0]
    thought = generate_response(
        f"Think deeply about this question:\n{top_q['question']}",
        model=get_thinking_model()
    )
    update_working_memory(f"Curiosity: {top_q['question']} → {thought}")

    top_q["attempts"] += 1
    top_q["last_thought"] = datetime.now(timezone.utc).isoformat()
    top_q["satisfaction"] = rate_satisfaction(thought)

    if top_q["satisfaction"] >= 0.95:
        top_q["status"] = "resolved"
        update_working_memory(f"✅ Resolved curiosity: {top_q['question']} → {thought}")

        if os.path.exists(CORE_MEMORY_FILE):
            with open(CORE_MEMORY_FILE, "a") as cm:
                cm.write(f"\n\n# Resolved Curiosity\n- {top_q['question']} → {thought.strip()[:300]}")

    save_json(CURIOUS_GEORGE, curiosity)

def simulate_world_state_change(change_description):
    world_model = load_json(WORLD_MODEL, default_type=dict)
    if not isinstance(world_model, dict):
        log_error("⚠️ WORLD_MODEL is not a dict. Resetting to empty dict.")
        world_model = {}

    casual_rules = load_json(CASUAL_RULES, default_type=dict)
    if not isinstance(casual_rules, dict):
        log_error("⚠️ CASUAL_RULES is not a dict. Resetting to empty dict.")
        casual_rules = {}

    prompt = (
        f"I am Orrin, simulating a world model update.\n"
        f"Change description: '{change_description}'\n\n"
        "Here is my current internal world model:\n"
        f"{json.dumps(world_model, indent=2)}\n\n"
        "Here are my known causal rules:\n"
        f"{json.dumps(casual_rules, indent=2)}\n\n"
        "Predict the impact of this change using any applicable rules.\n"
        "Respond in JSON:\n"
        "{\n"
        "  \"entities_changed\": [\"...\"],\n"
        "  \"new_events\": [\"...\"],\n"
        "  \"belief_impacts\": [\"...\"],\n"
        "  \"rules_used\": [\"...\"]\n"
        "}"
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    result = extract_json(response)

    if not result:
        update_working_memory(f"Failed to simulate world change for: {change_description}")
        return None

    now = datetime.now(timezone.utc).isoformat()
    updated = False

    if isinstance(result.get("new_events"), list):
        world_model.setdefault("events", [])
        for e in result["new_events"]:
            world_model["events"].append({
                "description": e,
                "timestamp": now
            })
            updated = True

    if isinstance(result.get("entities_changed"), list):
        world_model.setdefault("entities", {})
        for ent in result["entities_changed"]:
            if ent in world_model["entities"]:
                world_model["entities"][ent].setdefault("history", []).append({
                    "change": change_description,
                    "timestamp": now
                })
                updated = True

    if updated:
        save_json(WORLD_MODEL, world_model)

    update_working_memory(
        f"Simulated world change: {change_description}\nResult: {json.dumps(result, indent=2)}"
    )

    with open(PRIVATE_THOUGHTS_FILE, "a") as f:
        f.write(f"\n[{now}] Orrin simulated a world change:\n{change_description}\nResult:\n{json.dumps(result, indent=2)}\n")

    return result