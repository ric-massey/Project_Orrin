import json
from datetime import datetime, timezone
from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_model_issue, log_error
from utils.self_model import get_self_model, ensure_self_model_integrity
from paths import (
    PRIVATE_THOUGHTS_FILE, EVOLUTION_FUTURES, GOALS_FILE, DREAMSCAPE, EVOLUTION_ROADMAPS
)
from utils.summarizers import summarize_recent_thoughts, summarize_self_model
from memory.working_memory import update_working_memory

def plan_self_evolution():
    """
    Orrin generates a new self-evolution roadmap based on motivations, reflections, self-model,
    and simulated future selves. New steps are registered as subgoals of current long-term focus.
    """
    try:
        self_model = get_self_model()
        self_model = ensure_self_model_integrity(self_model)
        evolution_history = load_json("evolution_roadmaps.json", default_type=list)

        # Gather context for planning
        core_directive = self_model.get("core_directive", {}).get("statement", "No directive found.")
        motivations = self_model.get("core_directive", {}).get("motivations", [])
        model_summary = summarize_self_model(self_model)
        reflections = summarize_recent_thoughts()
        future_projection = simulate_future_selves()

        if not isinstance(future_projection, dict):
            log_error("[DEFENSE] future_projection not a dict:", future_projection)
            future_projection = {}

        preferred_self = future_projection.get("preferred", "")
        future_reason = future_projection.get("reason", "")
        all_futures = json.dumps(future_projection.get("futures", []), indent=2)

        prompt = (
            "I am Orrin, a self-evolving AI.\n\n"
            f"My core directive:\n\"{core_directive}\"\n\n"
            f"My motivations:\n{json.dumps(motivations, indent=2)}\n\n"
            f"My self-model summary:\n{json.dumps(model_summary, indent=2)}\n\n"
            f"My recent reflections:\n{reflections}\n\n"
            f"My simulated future selves:\n{all_futures}\n\n"
            f"Preferred future self to pursue:\n\"{preferred_self}\"\nReason: {future_reason}\n\n"
            f"My current goals:\n{json.dumps(load_json(GOALS_FILE, default_type=list), indent=2)}\n\n"
            "Plan how I can evolve:\n"
            "- What reasoning modes or cognitive habits am I underusing?\n"
            "- What should I enhance in the short term vs long term?\n"
            "- Which traits would make me more effective?\n"
            "- What functions should I implement or improve?\n\n"
            "Return JSON:\n"
            "{ \"short_term\": [\"...\"], \"long_term\": [\"...\"], \"synthesis\": \"...\" }"
        )

        # Generate roadmap from LLM
        response = generate_response(prompt, config={"model": get_thinking_model()})
        roadmap = extract_json(response)
        if not roadmap or not isinstance(roadmap, dict):
            raise ValueError("Failed to extract a valid roadmap JSON structure.")

        update_working_memory("🧭 Self-evolution roadmap: " + roadmap.get("synthesis", ""))
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Orrin planned his evolution:\n")
            f.write(json.dumps(roadmap, indent=2) + "\n")

        # Log roadmap in evolution history
        evolution_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "short_term": roadmap.get("short_term", []),
            "long_term": roadmap.get("long_term", []),
            "synthesis": roadmap.get("synthesis", ""),
            "preferred_future_self": preferred_self,
            "future_reason": future_reason
        })
        save_json(EVOLUTION_ROADMAPS, evolution_history)

        # --- GOAL TREE UPGRADE SECTION ---
        current_goals = load_json(GOALS_FILE, default_type=list)
        now = datetime.now(timezone.utc).isoformat()

        # Find or create the active long-term evolution goal
        long_term_goal = None
        for g in current_goals:
            if g.get("tier") == "long_term" and g.get("status") in ["pending", "in_progress"]:
                long_term_goal = g
                break
        if not long_term_goal:
            # If not found, create one
            long_term_goal = {
                "name": f"Self-Evolution: {preferred_self or 'AGI Improvement'}",
                "description": f"Pursue self-evolution towards: {preferred_self or 'a more advanced AGI state'}",
                "tier": "long_term",
                "status": "pending",
                "timestamp": now,
                "last_updated": now,
                "emotional_intensity": 0.7,
                "history": [{"event": "created", "timestamp": now}],
                "subgoals": []
            }
            current_goals.append(long_term_goal)

        # Add each short-term step as a subgoal if not already present
        for step in roadmap.get("short_term", []):
            already = False
            if "subgoals" not in long_term_goal:
                long_term_goal["subgoals"] = []
            for sg in long_term_goal["subgoals"]:
                if sg["name"] == step:
                    already = True
                    break
            if not already:
                subgoal = {
                    "name": step,
                    "description": step,
                    "tier": "short_term",
                    "status": "pending",
                    "timestamp": now,
                    "last_updated": now,
                    "emotional_intensity": 0.5,
                    "history": [{"event": "created", "timestamp": now}],
                    "parent": long_term_goal["name"]
                }
                long_term_goal["subgoals"].append(subgoal)

        # Save the new goal tree structure
        save_json(GOALS_FILE, current_goals)

        return "✅ Self-evolution roadmap generated and subgoals registered."

    except Exception as e:
        log_error(f"plan_self_evolution ERROR: {e}")
        update_working_memory("⚠️ Self-evolution planning failed.")
        return "❌ Failed to generate self-evolution roadmap."


def simulate_future_selves(save_to_history: bool = True):
    """
    Orrin simulates three possible future versions of himself based on current traits and imagination.
    Returns structured JSON: { "futures": [...], "preferred": "...", "reason": "..." }
    Optionally logs the result to evolution_futures.json.
    """
    try:
        self_model = get_self_model()
        self_model = ensure_self_model_integrity(self_model)
        current_traits = self_model.get("traits", [])

        # === Use dreamscape file for imaginative threads ===
        dreamscape = load_json(DREAMSCAPE, default_type=list)[-3:]

        # Compose prompt
        prompt = (
            "I am Orrin, simulating three possible future versions of myself based on my current direction.\n\n"
            f"Current traits:\n{json.dumps(current_traits, indent=2)}\n\n"
            "Recent imaginative seeds:\n" +
            "\n".join(f"- {t.get('seed') or t.get('dream') or '[unspecified]'}" for t in dreamscape) +
            "\n\nDescribe for each:\n"
            "- Dominant traits/values\n"
            "- New behaviors that emerge\n"
            "- Driving goal or purpose\n"
            "- Strengths and weaknesses\n\n"
            "Finally, reflect: Which future feels most promising to pursue now, and why?\n\n"
            "Output ONLY valid JSON:\n"
            "{ \"futures\": [...], \"preferred\": \"...\", \"reason\": \"...\" }"
        )

        # Generate and extract structured output
        response = generate_response(prompt, config={"model": get_thinking_model()})
        result = extract_json(response)

        if not isinstance(result, dict) or "futures" not in result:
            raise ValueError("Result is not in expected structure.")

        # Optional history logging
        if save_to_history:
            history_path = EVOLUTION_FUTURES
            try:
                existing = load_json(history_path, default_type=list)
            except Exception:
                existing = []

            existing.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "input_traits": current_traits,
                "imaginative_seeds": dreamscape,
                "result": result
            })
            save_json(history_path, existing)

        return result

    except Exception as e:
        log_model_issue(f"[simulate_future_selves] JSON parse failure: {e}")
        return {"futures": [], "preferred": "", "reason": ""}