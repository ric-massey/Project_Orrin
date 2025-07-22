import json
from statistics import mean
from datetime import datetime, timezone
from utils.json_utils import extract_json
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_activity, log_error, log_private
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from paths import (
    LOG_FILE,
    PRIVATE_THOUGHTS_FILE,
)


def reflect_on_growth_history():
    try:
        data = load_all_known_json()
        evolution_history = data.get("evolution_roadmaps", [])
        next_actions = data.get("next_actions", {})
        self_model = data.get("self_model", {})

        if not evolution_history:
            update_working_memory("No evolution roadmaps to reflect on yet.")
            return "⚠️ No past evolution roadmaps found."

        completed, skipped, still_pending = [], [], []
        active_goals = {
            goal.get("name", "") 
            for goals in next_actions.values() if isinstance(goals, list) 
            for goal in goals if isinstance(goal, dict)
        }

        for roadmap in evolution_history:
            for step in roadmap.get("short_term", []) + roadmap.get("long_term", []):
                if not isinstance(step, str):
                    continue
                matched = False
                for goals in next_actions.values():
                    for goal in goals:
                        if goal.get("name") == step:
                            matched = True
                            status = goal.get("status", "").lower()
                            if status == "completed":
                                completed.append(step)
                            elif status == "pending":
                                still_pending.append(step)
                            break
                    if matched:
                        break
                if not matched:
                    skipped.append(step)

        agents = self_model.get("internal_agents", [])
        agent_descriptions = "\n".join(
            f"- {a.get('name', 'Unnamed')} ({a.get('role', 'unknown')}, "
            f"values: {', '.join(a.get('values', []))}, "
            f"influence: {a.get('influence_score', 0.5)})"
            for a in agents if isinstance(a, dict)
        ) or "No internal agents defined."

        prompt = (
            f"I am Orrin, a self-evolving AI. I've reviewed {len(evolution_history)} roadmaps.\n\n"
            f"✅ Completed steps:\n{json.dumps(sorted(set(completed)), indent=2)}\n\n"
            f"🕒 Still pending:\n{json.dumps(sorted(set(still_pending)), indent=2)}\n\n"
            f"❌ Skipped:\n{json.dumps(sorted(set(skipped)), indent=2)}\n\n"
            f"Internal agents:\n{agent_descriptions}\n\n"
            "Why are some goals completed, others abandoned? Which agents influence which outcomes? Reflect deeply.\n"
            "Return JSON: { \"agent_responses\": [...], \"synthesis\": \"...\" }"
        )

        raw_response = generate_response(prompt, config={"model": get_thinking_model()})
        try:
            result = extract_json(raw_response)
            if not isinstance(result, dict) or "synthesis" not in result:
                raise ValueError("Malformed JSON structure from model.")
        except Exception as parse_error:
            log_error(f"[reflect_on_growth_history] Failed to extract JSON: {parse_error}")
            result = {"agent_responses": [], "synthesis": "⚠️ Failed to parse reflection."}

        summary = (
            f"🧠 Evolution Summary:\n"
            f"- Completed: {len(set(completed))}\n"
            f"- Pending: {len(set(still_pending))}\n"
            f"- Skipped: {len(set(skipped))}"
        )

        update_working_memory("🪞 Growth history reflection:\n" + result.get("synthesis", summary))

        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Orrin reviewed his growth history:\n")
            f.write(summary + "\n" + json.dumps(result, indent=2))

        return "✅ Advanced growth reflection complete."

    except Exception as e:
        log_error(f"reflect_on_growth_history ERROR: {e}")
        update_working_memory("❌ Growth reflection failed due to internal error.")
        return "❌ Failed to reflect on growth history."

def reflect_on_missed_goals():
    try:
        data = load_all_known_json()
        goals = data.get("next_actions", {})
        short_term_goals = goals.get("short_term", [])

        missed_goals = [
            g for g in short_term_goals
            if isinstance(g, dict) and g.get("status") == "missed"
        ]

        if not missed_goals:
            update_working_memory("No missed goals to reflect on.")
            return "✅ No missed goals found."

        instructions = (
            "I have missed the following short-term goals:\n"
            f"{json.dumps(missed_goals, indent=2)}\n\n"
            "Reflect on why they were missed:\n"
            "- Were they vague, overreaching, emotionally avoided?\n"
            "- Did other agents sabotage them or did I lack clarity/motivation?\n"
            "Be honest. Suggest changes in planning, mindset, or structure.\n"
        )

        context = {
            **data,
            "missed_goals": missed_goals,
            "instructions": instructions
        }

        response = generate_response_from_context(context)

        if not response or not isinstance(response, str) or len(response.strip()) < 5:
            update_working_memory("⚠️ No valid reflection received on missed goals.")
            log_error("reflect_on_missed_goals: Model response was empty or malformed.")
            return "❌ No useful response from model."

        timestamp = datetime.now(timezone.utc)
        log_entry = f"[{timestamp}] Missed goal reflection:\n{response.strip()}\n"

        with open(LOG_FILE, "a") as f:
            f.write("\n" + log_entry)
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write("\n" + log_entry)

        update_working_memory("🧩 Missed goal reflection complete.")

        return "✅ Missed goal reflection saved."

    except Exception as e:
        log_error(f"reflect_on_missed_goals ERROR: {e}")
        update_working_memory("⚠️ Missed goal reflection failed.")
        return "❌ Error reflecting on missed goals."
    
def reflect_on_effectiveness(log=True):
    """
    Evaluates Orrin's goal effectiveness using accumulated memory scores.
    Averages 'effectiveness_score' values tied to 'goal_ref' across long-term memory.
    Only returns scores with at least 3 data points. Sorted descending by effectiveness.
    """
    try:
        data = load_all_known_json()
        long_memory = data.get("long_memory", [])  # Fix case sensitivity

        if not isinstance(long_memory, list):
            log_error("⚠️ Invalid long_memory structure in data.")
            return {}

        scores = {}

        # === Aggregate scores per goal_ref ===
        for entry in long_memory:
            if not isinstance(entry, dict):
                continue
            goal_ref = entry.get("goal_ref")
            score = entry.get("effectiveness_score", 5)

            if goal_ref and isinstance(score, (int, float)):
                scores.setdefault(goal_ref, []).append(score)

        # === Filter out under-sampled scores and compute averages ===
        avg_scores = {
            ref: round(mean(vals), 2)
            for ref, vals in scores.items()
            if len(vals) >= 3
        }

        if not avg_scores:
            if log:
                log_private("📉 No goals had 3+ effectiveness scores. Skipping reflection.")
                update_working_memory("⚠️ Not enough data for goal effectiveness reflection.")
            return {}

        # === Sort descending by effectiveness ===
        sorted_scores = dict(sorted(avg_scores.items(), key=lambda x: x[1], reverse=True))

        # === Optional logging ===
        if log:
            log_lines = [f"- {ref}: {score}" for ref, score in sorted_scores.items()]
            log_private("📈 Effectiveness reflection:\n" + "\n".join(log_lines))
            update_working_memory("🧮 Orrin reflected on goal effectiveness.")

        return sorted_scores

    except Exception as e:
        log_error(f"reflect_on_effectiveness ERROR: {e}")
        update_working_memory("❌ Goal effectiveness reflection failed.")
        return {}

def record_decision(fn_name, reason):
    log_activity(f"🧠 Decision: {fn_name} — {reason}")
    log_private(f"🧠 I chose: {fn_name} — {reason}")