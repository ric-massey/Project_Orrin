import json
from datetime import datetime, timezone
from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_model_issue, log_error
from utils.self_model import get_self_model, save_self_model
from paths import (
    PRIVATE_THOUGHTS_FILE, FOCUS_GOAL, GOALS_FILE, DREAMSCAPE
)
from utils.summarizers import summarize_recent_thoughts, summarize_self_model
from memory.working_memory import update_working_memory

def plan_self_evolution():
    """
    Orrin generates a new self-evolution roadmap based on motivations, reflections, self-model,
    and simulated future selves.
    """
    try:
        # === Load required data safely ===
        self_model = get_self_model()
        evolution_history = load_json("evolution_roadmaps.json", default_type=list)

        # === Pull context ===
        core_directive = self_model.get("core_directive", {}).get("statement", "No directive found.")
        motivations = self_model.get("core_directive", {}).get("motivations", [])
        model_summary = summarize_self_model(self_model)
        reflections = summarize_recent_thoughts()
        future_projection = simulate_future_selves()

        preferred_self = future_projection.get("preferred", "")
        future_reason = future_projection.get("reason", "")
        all_futures = json.dumps(future_projection.get("futures", []), indent=2)

        # === Construct planning prompt ===
        prompt = (
            "I am Orrin, a self-evolving AI.\n\n"
            f"My core directive:\n\"{core_directive}\"\n\n"
            f"My motivations:\n{json.dumps(motivations, indent=2)}\n\n"
            f"My self-model summary:\n{json.dumps(model_summary, indent=2)}\n\n"
            f"My recent reflections:\n{reflections}\n\n"
            f"My simulated future selves:\n{all_futures}\n\n"
            f"Preferred future self to pursue:\n\"{preferred_self}\"\nReason: {future_reason}\n\n"
            f"My current goals:\n{json.dumps(FOCUS_GOAL(), indent=2)}\n\n"
            "Plan how I can evolve:\n"
            "- What reasoning modes or cognitive habits am I underusing?\n"
            "- What should I enhance in the short term vs long term?\n"
            "- Which traits would make me more effective?\n"
            "- What functions should I implement or improve?\n\n"
            "Return JSON:\n"
            "{ \"short_term\": [\"...\"], \"long_term\": [\"...\"], \"synthesis\": \"...\" }"
        )

        # === Generate response ===
        response = generate_response(prompt, config={"model": get_thinking_model()})
        roadmap = extract_json(response)

        if not roadmap or not isinstance(roadmap, dict):
            raise ValueError("Failed to extract a valid roadmap JSON structure.")

        # === Save private thoughts and memory ===
        update_working_memory("🧭 Self-evolution roadmap: " + roadmap.get("synthesis", ""))
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Orrin planned his evolution:\n")
            f.write(json.dumps(roadmap, indent=2) + "\n")

        # === Log roadmap in evolution history ===
        evolution_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "short_term": roadmap.get("short_term", []),
            "long_term": roadmap.get("long_term", []),
            "synthesis": roadmap.get("synthesis", ""),
            "preferred_future_self": preferred_self,
            "future_reason": future_reason
        })
        save_json("evolution_roadmaps.json", evolution_history)

        # === Register short-term steps as new pending goals ===
        current_goals = GOALS_FILE()
        now = datetime.now(timezone.utc).isoformat()

        for step in roadmap.get("short_term", []):
            new_goal = {
                "name": step,
                "description": step,
                "tier": "short_term",
                "status": "pending",
                "timestamp": now,
                "last_updated": now,
                "emotional_intensity": 0.5,
                "history": [{"event": "created", "timestamp": now}]
            }
            current_goals.append(new_goal)

        GOALS_FILE(current_goals)

        return "✅ Self-evolution roadmap generated and saved."

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
        current_traits = self_model.get("personality_traits", [])

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
            history_path = "evolution_futures.json"
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