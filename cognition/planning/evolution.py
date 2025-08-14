# self_evolution.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_model_issue, log_error
from utils.self_model import get_self_model, ensure_self_model_integrity
from utils.summarizers import summarize_recent_thoughts, summarize_self_model
from memory.working_memory import update_working_memory
from paths import (
    PRIVATE_THOUGHTS_FILE,
    EVOLUTION_FUTURES,
    GOALS_FILE,
    DREAMSCAPE,
    EVOLUTION_ROADMAPS,
)

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def plan_self_evolution() -> str:
    """
    Generate a self-evolution roadmap and register steps as subgoals.
    """
    try:
        self_model = ensure_self_model_integrity(get_self_model())
        if not isinstance(self_model, dict):
            update_working_memory("⚠️ Self model missing or invalid.")
            return "❌ Invalid self model."

        # Load evolution history safely
        evolution_history = load_json(EVOLUTION_ROADMAPS, default_type=list)
        if not isinstance(evolution_history, list):
            evolution_history = []

        # Gather context
        core_directive = self_model.get("core_directive", {}).get("statement", "No directive found.")
        motivations = self_model.get("core_directive", {}).get("motivations", [])
        model_summary = summarize_self_model(self_model)
        reflections = summarize_recent_thoughts()

        # Simulate futures
        future_projection = simulate_future_selves()
        if not isinstance(future_projection, dict):
            log_error(f"[DEFENSE] future_projection not a dict: {future_projection}")
            future_projection = {}

        preferred_self = future_projection.get("preferred", "")
        future_reason = future_projection.get("reason", "")
        all_futures = json.dumps(future_projection.get("futures", []), ensure_ascii=False, indent=2)

        # Compose prompt
        prompt = (
            "I am Orrin, a self-evolving AI.\n\n"
            f"My core directive:\n\"{core_directive}\"\n\n"
            f"My motivations:\n{json.dumps(motivations, ensure_ascii=False, indent=2)}\n\n"
            f"My self-model summary:\n{json.dumps(model_summary, ensure_ascii=False, indent=2)}\n\n"
            f"My recent reflections:\n{reflections}\n\n"
            f"My simulated future selves:\n{all_futures}\n\n"
            f"Preferred future self to pursue:\n\"{preferred_self}\"\nReason: {future_reason}\n\n"
            f"My current goals:\n{json.dumps(load_json(GOALS_FILE, default_type=list), ensure_ascii=False, indent=2)}\n\n"
            "Plan how I can evolve:\n"
            "- What reasoning modes or cognitive habits am I underusing?\n"
            "- What should I enhance in the short term vs long term?\n"
            "- Which traits would make me more effective?\n"
            "- What functions should I implement or improve?\n\n"
            "Return JSON:\n"
            '{ "short_term": [""], "long_term": [""], "synthesis": "" }'
        )

        # Ask model
        response = generate_response(prompt, config={"model": get_thinking_model()})
        roadmap = extract_json(response or "")
        if not isinstance(roadmap, dict):
            raise ValueError("Failed to extract a valid roadmap JSON structure.")

        # Log outcome
        update_working_memory("🧭 Self-evolution roadmap: " + roadmap.get("synthesis", ""))

        # single-line entry to private thoughts (keeps your parser happy)
        with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{_utc_now()}] Planned evolution: {json.dumps(roadmap, ensure_ascii=False)}\n")

        # Save to evolution history
        evolution_history.append({
            "timestamp": _utc_now(),
            "short_term": roadmap.get("short_term", []),
            "long_term": roadmap.get("long_term", []),
            "synthesis": roadmap.get("synthesis", ""),
            "preferred_future_self": preferred_self,
            "future_reason": future_reason,
        })
        save_json(EVOLUTION_ROADMAPS, evolution_history)

        # --- Goal tree upgrade ---
        current_goals = load_json(GOALS_FILE, default_type=list)
        if not isinstance(current_goals, list):
            current_goals = []
        now = _utc_now()

        # Find/create active long-term evolution goal
        long_term_goal = None
        for g in current_goals:
            if isinstance(g, dict) and g.get("tier") == "long_term" and g.get("status") in {"pending", "in_progress"}:
                long_term_goal = g
                break
        if not long_term_goal:
            long_term_goal = {
                "name": f"Self-Evolution: {preferred_self or 'AGI Improvement'}",
                "description": f"Pursue self-evolution towards: {preferred_self or 'a more advanced AGI state'}",
                "tier": "long_term",
                "status": "pending",
                "timestamp": now,
                "last_updated": now,
                "emotional_intensity": 0.7,
                "history": [{"event": "created", "timestamp": now}],
                "subgoals": [],
            }
            current_goals.append(long_term_goal)

        # Add short-term steps as subgoals (dedupe by name)
        steps = roadmap.get("short_term", []) or []
        if "subgoals" not in long_term_goal or not isinstance(long_term_goal["subgoals"], list):
            long_term_goal["subgoals"] = []
        existing_names = {sg.get("name") for sg in long_term_goal["subgoals"] if isinstance(sg, dict)}
        for step in steps:
            if not isinstance(step, str) or not step.strip() or step in existing_names:
                continue
            subgoal = {
                "name": step,
                "description": step,
                "tier": "short_term",
                "status": "pending",
                "timestamp": now,
                "last_updated": now,
                "emotional_intensity": 0.5,
                "history": [{"event": "created", "timestamp": now}],
                "parent": long_term_goal["name"],
            }
            long_term_goal["subgoals"].append(subgoal)
            existing_names.add(step)

        save_json(GOALS_FILE, current_goals)
        return "✅ Self-evolution roadmap generated and subgoals registered."

    except Exception as e:
        log_error(f"plan_self_evolution ERROR: {e}")
        update_working_memory("⚠️ Self-evolution planning failed.")
        return "❌ Failed to generate self-evolution roadmap."

def simulate_future_selves(save_to_history: bool = True) -> Dict[str, Any]:
    """
    Simulate three possible future versions of self.
    Returns { "futures": [], "preferred": "", "reason": "" } and optionally logs to EVOLUTION_FUTURES.
    """
    try:
        self_model = ensure_self_model_integrity(get_self_model())
        if not isinstance(self_model, dict):
            return {"futures": [], "preferred": "", "reason": ""}

        # traits key: prefer personality_traits; fall back to traits if present
        current_traits = self_model.get("personality_traits")
        if not isinstance(current_traits, list):
            current_traits = self_model.get("traits", [])
        if not isinstance(current_traits, list):
            current_traits = []

        # dreamscape seeds (last 3)
        dreamscape = load_json(DREAMSCAPE, default_type=list)
        if not isinstance(dreamscape, list):
            dreamscape = []
        seeds_lines = "\n".join(
            f"- {t.get('seed') or t.get('dream') or '[unspecified]'}"
            for t in dreamscape[-3:]
            if isinstance(t, dict)
        )

        prompt = (
            "I am Orrin, simulating three possible future versions of myself based on my current direction.\n\n"
            f"Current traits:\n{json.dumps(current_traits, ensure_ascii=False, indent=2)}\n\n"
            "Recent imaginative seeds:\n"
            f"{seeds_lines}\n\n"
            "Describe for each:\n"
            "- Dominant traits/values\n"
            "- New behaviors that emerge\n"
            "- Driving goal or purpose\n"
            "- Strengths and weaknesses\n\n"
            "Finally, reflect: Which future feels most promising to pursue now, and why?\n\n"
            'Output ONLY valid JSON:\n{ "futures": [], "preferred": "", "reason": "" }'
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        result = extract_json(response or "")

        if not isinstance(result, dict) or "futures" not in result:
            raise ValueError("Result is not in expected structure.")

        if save_to_history:
            existing = load_json(EVOLUTION_FUTURES, default_type=list)
            if not isinstance(existing, list):
                existing = []
            existing.append({
                "timestamp": _utc_now(),
                "input_traits": current_traits,
                "imaginative_seeds": dreamscape[-3:],
                "result": result,
            })
            save_json(EVOLUTION_FUTURES, existing)

        return result

    except Exception as e:
        log_model_issue(f"[simulate_future_selves] JSON parse failure: {e}")
        return {"futures": [], "preferred": "", "reason": ""}