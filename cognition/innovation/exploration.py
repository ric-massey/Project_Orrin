# exploration.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from utils.core_utils import extract_questions, rate_satisfaction
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json, save_json
from utils.append import append_to_json
from memory.working_memory import update_working_memory
from utils.log import log_error

from paths import (
    CURIOUS_GEORGE,
    CORE_MEMORY_FILE,
    WORLD_MODEL,
    CASUAL_RULES,            # note: txt in your paths
    PRIVATE_THOUGHTS_FILE,
    ensure_files,
)

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def curiosity_loop() -> str | None:
    curiosity = load_json(CURIOUS_GEORGE, default_type=list)
    if not isinstance(curiosity, list):
        log_error("⚠️ CURIOUS_GEORGE is not a list. Resetting to empty list.")
        curiosity = []

    # Seed questions if none exist
    if not curiosity:
        prompt = "What am I currently curious about? What questions do I have about myself, the user, or the world?"
        new_qs = generate_response(prompt, config={"model": get_thinking_model()})
        if new_qs:
            for q in extract_questions(new_qs):
                curiosity.append({
                    "question": q,
                    "status": "open",
                    "attempts": 0,
                    "satisfaction": 0.0,
                    "last_thought": _utc_now(),
                })
            save_json(CURIOUS_GEORGE, curiosity)

    open_qs = [q for q in curiosity if isinstance(q, dict) and q.get("status") == "open"]
    if not open_qs:
        return None

    # Highest dissatisfaction first (you used max by satisfaction; keep your sort but clarify)
    top_q = sorted(open_qs, key=lambda q: -float(q.get("satisfaction", 0.0)))[0]

    thought = generate_response(
        f"Think deeply about this question:\n{top_q.get('question','(missing)')}",
        config={"model": get_thinking_model()},
    ) or ""

    update_working_memory(f"Curiosity: {top_q.get('question','(missing)')} → {thought}")

    top_q["attempts"] = int(top_q.get("attempts", 0)) + 1
    top_q["last_thought"] = _utc_now()
    top_q["satisfaction"] = float(rate_satisfaction(thought))

    if top_q["satisfaction"] >= 0.95:
        top_q["status"] = "resolved"
        update_working_memory(f"✅ Resolved curiosity: {top_q.get('question','(missing)')} → {thought}")

        # Append a structured JSON entry to CORE_MEMORY_FILE (don’t corrupt it with raw text)
        append_to_json(CORE_MEMORY_FILE, {
            "event": "resolved_curiosity",
            "question": top_q.get("question"),
            "answer": (thought or "").strip()[:300],
            "timestamp": _utc_now(),
        })

    save_json(CURIOUS_GEORGE, curiosity)
    return top_q.get("status")

def _load_causal_rules_text() -> str:
    """CASUAL_RULES is a .txt in your paths; read as text."""
    try:
        p = Path(CASUAL_RULES)
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception:
        pass
    return "(no causal rules text available)"

def simulate_world_state_change(change_description: str) -> Dict[str, Any] | None:
    world_model = load_json(WORLD_MODEL, default_type=dict)
    if not isinstance(world_model, dict):
        log_error("⚠️ WORLD_MODEL is not a dict. Resetting to empty dict.")
        world_model = {}

    causal_rules_text = _load_causal_rules_text()

    prompt = (
        "I am Orrin, simulating a world model update.\n"
        f"Change description: '{change_description}'\n\n"
        "Here is my current internal world model:\n"
        f"{json.dumps(world_model, ensure_ascii=False, indent=2)}\n\n"
        "Here are my known causal rules (text):\n"
        f"{causal_rules_text}\n\n"
        "Predict the impact of this change using any applicable rules.\n"
        "Respond in JSON:\n"
        "{\n"
        '  "entities_changed": [""],\n'
        '  "new_events": [""],\n'
        '  "belief_impacts": [""],\n'
        '  "rules_used": [""]\n'
        "}"
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    result = extract_json(response or "")

    if not result:
        update_working_memory(f"Failed to simulate world change for: {change_description}")
        return None

    now = _utc_now()
    updated = False

    # Add new events
    if isinstance(result.get("new_events"), list):
        world_model.setdefault("events", [])
        for e in result["new_events"]:
            if not isinstance(e, str):
                continue
            world_model["events"].append({"description": e, "timestamp": now})
            updated = True

    # Track entity changes
    if isinstance(result.get("entities_changed"), list):
        world_model.setdefault("entities", {})
        for ent in result["entities_changed"]:
            if not isinstance(ent, str):
                continue
            world_model["entities"].setdefault(ent, {}).setdefault("history", []).append(
                {"change": change_description, "timestamp": now}
            )
            updated = True

    if updated:
        save_json(WORLD_MODEL, world_model)

    update_working_memory(
        f"Simulated world change: {change_description}\nResult: {json.dumps(result, ensure_ascii=False, indent=2)}"
    )

    # Write a single-line entry to PRIVATE_THOUGHTS_FILE (so your line parser stays happy)
    ensure_files([Path(PRIVATE_THOUGHTS_FILE)])
    with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] World change: {change_description} | {json.dumps(result, ensure_ascii=False)}\n")

    return result