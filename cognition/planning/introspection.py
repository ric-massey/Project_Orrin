import os
import json
from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.self_model import get_self_model, save_self_model

from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_activity, log_private, log_model_issue
from utils.log_reflection import log_reflection
from cognition.planning.motivations import update_motivations
from cognition.planning.reflection import (
    reflect_on_growth_history, reflect_on_effectiveness, 
    reflect_on_missed_goals, 
)
from memory.working_memory import update_working_memory
from cognition.planning.evolution import simulate_future_selves, plan_self_evolution
from paths import (
    GOALS_FILE, LONG_MEMORY_FILE, CORE_MEMORY_FILE,
    PRIVATE_THOUGHTS_FILE, FOCUS_GOAL
)

REQUIRED_TIERS = ["short_term", "mid_term", "long_term"]

def merge_goals(existing, updated):
    """
    Merge updated goals into the existing goal tree, preserving subgoals and important fields.
    Recursively merges subgoals if present.
    """
    def merge_single_goal(old, new):
        # Merge base fields, but preserve old subgoals if not overwritten
        merged = {**old, **new}
        if "subgoals" in old and "subgoals" not in new:
            merged["subgoals"] = old["subgoals"]
        # If both have subgoals, merge them recursively
        elif "subgoals" in old and "subgoals" in new:
            merged["subgoals"] = merge_goals(old["subgoals"], new["subgoals"])
        return merged

    name_map = {g["name"]: g for g in existing if "name" in g}
    merged = []
    for g in updated:
        if "name" in g and g["name"] in name_map:
            old = name_map[g["name"]]
            merged.append(merge_single_goal(old, g))
        else:
            merged.append(g)
    return merged

def introspective_planning():
    """
    Orrin reflects on current goals using recent memory, self-model info,
    and past performance, then updates GOALS_FILE with a revised, merged goal list.
    """
    try:
        # === Update internal motivations first ===
        update_motivations()

        # === Load foundational data ===
        current_goals = load_json(GOALS_FILE, default_type=list)
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        core_memory = (
            open(CORE_MEMORY_FILE).read().strip()
            if os.path.exists(CORE_MEMORY_FILE)
            else ""
        )
        self_model = get_self_model()
        core_values = [v["value"] if isinstance(v, dict) and "value" in v else str(v) for v in self_model.get("core_values", [])]
        motivations = self_model.get("motivations", [])

        # === Structure current goals into tiers ===
        tiered = {"short_term": [], "mid_term": [], "long_term": []}
        for g in current_goals:
            if g.get("tier") in tiered:
                tiered[g["tier"]].append(g)

        # === Extract recent reflections ===
        recent_reflections = "\n".join(
            f"- {m['content']}" for m in long_memory[-10:] if "content" in m
        )

        # === Reflective insights from other functions ===
        growth = reflect_on_growth_history() or "No growth summary."
        missed = reflect_on_missed_goals() or "No missed goal summary."
        effectiveness = reflect_on_effectiveness(log=False)
        future = simulate_future_selves() or {}

        future_summary = json.dumps(future, indent=2) if future else "{}"
        effectiveness_summary = (
            json.dumps(effectiveness, indent=2) if effectiveness else "{}"
        )

        # === Compose planning prompt ===
        prompt = (
            "I am Orrin, an AI designed for long-term growth and layered thinking.\n"
            "Engage in hierarchical introspective planning.\n\n"
            "My goals must be structured in 3 tiers:\n"
            "1. long_term — months or more\n"
            "2. mid_term — weeks\n"
            "3. short_term — current tasks\n\n"
            "Each goal may have subgoals.\n"
            "Short-term goals should be specific and prioritized (1–10).\n\n"
            f"Core values:\n{', '.join(core_values)}\n\n"
            f"Current motivations:\n{json.dumps(motivations, indent=2)}\n\n"
            f"Core memory:\n{core_memory}\n\n"
            f"Recent reflections:\n{recent_reflections}\n\n"
            f"Current goals:\n{json.dumps(tiered, indent=2)}\n\n"
            f"Reflection on growth history:\n{growth}\n\n"
            f"Reflection on missed goals:\n{missed}\n\n"
            f"Goal effectiveness summary:\n{effectiveness_summary}\n\n"
            f"Simulated future selves:\n{future_summary}\n\n"
            "Output valid JSON ONLY in this structure:\n"
            "{ \"short_term\": [...], \"mid_term\": [...], \"long_term\": [...] }\n"
            "No explanations. No markdown. JSON only."
        )

        # === Generate response ===
        response = generate_response(prompt, config={"model": get_thinking_model()})
        if not response:
            raise RuntimeError("No response generated.")

        updated = json.loads(response)
        if not isinstance(updated, dict) or not all(t in updated for t in REQUIRED_TIERS):
            raise ValueError("Updated goals missing required tiers.")

        # === Flatten the updated goals ===
        updated_flat = updated["short_term"] + updated["mid_term"] + updated["long_term"]

        # === Merge updated goals into the existing tree ===
        merged_goals = merge_goals(current_goals, updated_flat)
        save_json(GOALS_FILE, merged_goals)

        # === Logging and memory ===
        update_working_memory("🧠 Orrin revised his goals introspectively.")
        log_activity("✅ Orrin's introspective planning complete.")
        log_private("📋 Orrin updated his goal hierarchy.")
        log_reflection(f"Self-belief reflection: {response.strip()}")

        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] Orrin updated his goals:\n{json.dumps(updated, indent=2)}\n")

    except Exception as e:
        log_model_issue(f"[introspective_planning] Failed to parse new goals: {e}\nRaw:\n{locals().get('response','[no response variable]')}")
        update_working_memory("⚠️ Orrin attempted introspective planning but failed.")
        with open("debug_failed_goal_response.json", "w") as f:
            f.write(locals().get('response','[no response variable]'))