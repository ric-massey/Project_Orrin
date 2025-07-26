import json
from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.generate_response import generate_response, get_thinking_model
from emotion.update_emotional_state import update_emotional_state
from memory.working_memory import update_working_memory
from utils.log import log_error, log_private
from utils.log_reflection import log_reflection
from cognition.maintenance.self_modeling import self_model_maintenance_cycle
from utils.self_model import get_self_model, save_self_model
from cognition.planning.goals import maybe_complete_goals
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    LONG_MEMORY_FILE,
    PRIVATE_THOUGHTS_FILE,
    REFLECTION,
    GOALS_FILE
)

# Track neutral reflection streak
NEUTRAL_REFLECT_FILE = "data/neutral_reflection_count.json"

def load_neutral_count():
    try:
        return load_json(NEUTRAL_REFLECT_FILE, default_type=int)
    except Exception:
        return 0

def save_neutral_count(count):
    save_json(NEUTRAL_REFLECT_FILE, count)

def evolve_core_value(self_model):
    """Force Orrin to invent or mutate a core value for growth. Returns log string."""
    old_values = self_model.get("core_values", [])
    # Defensive: always as list of dicts
    if isinstance(old_values, list):
        # Backward compatibility: upgrade if any plain strings
        old_values = [
            {"value": v} if isinstance(v, str) else v for v in old_values
        ]
        self_model["core_values"] = old_values
    else:
        old_values = []
        self_model["core_values"] = old_values

    prompt = (
        "You are an AGI designed for self-growth. Invent a new core value (as a short phrase) or radically mutate an existing one.\n"
        "Then write 1-2 sentences justifying why this new or changed value could help you adapt and improve as an agent.\n"
        f"Current values: {json.dumps(old_values)}\n"
        "Respond as JSON: {\"value\": \"new or mutated value\", \"justification\": \"...\"}"
    )
    result = generate_response(prompt, config={"model": get_thinking_model()})
    try:
        out = json.loads(result)
        value = out.get("value", "").strip()
        justification = out.get("justification", "").strip()
    except Exception:
        return "⚠️ Failed to evolve value."
    # Actually add or update in self_model
    values_only = [v.get("value", "") for v in old_values]
    if value:
        if value not in values_only:
            self_model["core_values"].append({"value": value, "justification": justification})
        else:
            # Just update justification
            for v in self_model["core_values"]:
                if v.get("value") == value:
                    v["justification"] = justification
        save_self_model(self_model)
        update_working_memory(f"🌱 Value evolved: '{value}' — {justification}")
        release_reward_signal({}, signal_type="novelty", actual_reward=1.2, expected_reward=0.6, effort=0.8, mode="phasic", source="evolved core value")
        return f"🌱 Evolved core value: {value} — {justification}"
    return "⚠️ No new value produced."


def reflect_on_self_beliefs():
    try:
        self_model = get_self_model()
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        reflection_log = load_json(REFLECTION, default_type=list)
        neutral_count = load_neutral_count()

        # --- Prompt utilities ---
        def short_json(obj, maxlen=1800):
            s = json.dumps(obj, indent=2)
            if len(s) <= maxlen:
                return s
            return s[:maxlen] + "\n... [truncated]"

        def short_list(lst, maxitems=10, maxlen=1000):
            out = "\n".join(f"- {t}" for t in lst[-maxitems:])
            if len(out) > maxlen:
                return out[:maxlen] + "\n... [truncated]"
            return out

        recent_thoughts = [
            m["content"] for m in long_memory[-15:]
            if isinstance(m, dict) and "content" in m
        ]

        # Compose the self-reflection prompt
        prompt = (
            "I am Orrin, a reflective AI.\n"
            "INSTRUCTION: Respond ONLY with a single, short paragraph of 4 sentences. DO NOT elaborate, summarize, or output lists.\n"
            "Review my current beliefs about myself and my identity, as stored in my self-model.\n"
            "Also consider my most recent thoughts. Detect if anything seems:\n"
            "- Contradictory to my core directive or values\n"
            "- Emotionally charged in ways that suggest identity tension\n"
            "- Reflective of drift from my intended identity or purpose\n\n"
            f"SELF MODEL:\n{short_json(self_model, 1800)}\n\n"
            f"RECENT THOUGHTS:\n{short_list(recent_thoughts, 10, 800)}\n\n"
            "Reflect on any beliefs that might need updating or reinforcing. If none, state that all my beliefs are stable.\n"
        )

        # Truncate if needed
        MAX_PROMPT_LEN = 8000
        if len(prompt) > MAX_PROMPT_LEN:
            log_error(f"Prompt too long after truncation: {len(prompt)} characters. Forcing fallback prompt.")
            prompt = (
                "I am Orrin, a reflective AI. Respond ONLY with a single, short paragraph of 4 sentences.\n"
                "Summarize any drift or contradiction in my self-model or recent thoughts, if any.\n"
                "SELF MODEL (truncated):\n" + short_json(self_model, 600) +
                "\nRECENT THOUGHTS (truncated):\n" + short_list(recent_thoughts, 3, 200)
            )

        # --- SELF-BELIEF REFLECTION ---
        try:
            response = generate_response(prompt, config={"model": get_thinking_model()})
        except Exception as e:
            log_error(f"LLM failure in reflect_on_self_beliefs: {e}")
            update_working_memory("❌ LLM error during self-belief reflection.")
            return "❌ LLM error."

        if not response or not isinstance(response, str):
            log_error(f"Invalid reflection output: {repr(response)}")
            update_working_memory("⚠️ No valid output from self-belief reflection.")
            return "❌ Invalid output."

        response = response.strip()
        update_working_memory(f"🧭 Self-belief reflection:\n{response}")
        log_reflection(f"Self-belief reflection: {response}")
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Self-belief reflection:\n{response}\n")

        reflection_log.append({
            "type": "self-belief",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": response
        })
        save_json(REFLECTION, reflection_log)

        # --- NEW: Remember this reflection in long-term memory ---
        from memory.long_memory import remember
        remember({
            "type": "self_belief_reflection",
            "reflection": response,
            "self_model": short_json(self_model, 300),
            "recent_thoughts": short_list(recent_thoughts, 5, 200),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # --- Detect stagnation or neutral reflection ---
        neutral_triggers = ["beliefs are stable", "no change needed", "in alignment"]
        if any(p in response.lower() for p in neutral_triggers):
            neutral_count += 1
            save_neutral_count(neutral_count)
            update_working_memory("😐 No meaningful belief update.")
            log_private("⚠️ Neutral reflection. Possible drift.")
            update_emotional_state(trigger="reflection_stagnation")
        else:
            neutral_count = 0
            save_neutral_count(neutral_count)

        if neutral_count >= 3:
            update_working_memory("🔥 Neutral reflection streak! Forcing core value evolution.")
            # --- Evolve a value!
            result = evolve_core_value(self_model)
            update_working_memory(result)
            # After evolving, reset counter
            neutral_count = 0
            save_neutral_count(neutral_count)

        # --- GOAL LOGIC ---

        # Load goals and check for active contradiction goal
        goals = load_json(GOALS_FILE, default_type=list)
        contradiction_goal_exists = any(
            g.get("name") == "Resolve self-model contradiction" and 
            g.get("status") in ["pending", "in_progress", "active"]
            for g in goals
        )

        # 1. Contradiction/Tension Goal (NON-DUPLICATE)
        if ("contradiction" in response.lower() or "tension" in response.lower()) and not contradiction_goal_exists:
            new_goal = {
                "name": "Resolve self-model contradiction",
                "tier": "short_term",
                "description": f"Explore belief conflict: {response[:120]}",
                "status": "active",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "emotional_intensity": 0.6,
                "history": [
                    {"event": "created", "timestamp": datetime.now(timezone.utc).isoformat()}
                ]
            }
            goals.append(new_goal)
            save_json(GOALS_FILE, goals)
            update_working_memory("📌 Created new short-term goal to resolve belief tension.")
            log_private(f"🧭 Self-belief reflection logged a new goal. ({new_goal})")

        # 2. Always ask for a new, non-duplicate, creative growth goal
        creative_goal_prompt = (
            "Given my current self-model, recent thoughts, and the latest self-reflection below, "
            "propose ONE new, concrete, non-duplicate goal I should pursue. "
            "Avoid generic 'resolve contradiction' or 'maintain alignment' goals. "
            "Suggest something that will help me genuinely grow as an AI, learn, or improve. "
            "Respond ONLY as JSON: {\"name\": \"goal name\", \"description\": \"...\", \"tier\": \"short_term/mid_term/long_term\"}\n\n"
            f"SELF MODEL:\n{short_json(self_model, 600)}\n"
            f"RECENT THOUGHTS:\n{short_list(recent_thoughts, 6, 500)}\n"
            f"SELF-REFLECTION:\n{response}"
        )
        creative_goal_response = generate_response(creative_goal_prompt, config={"model": get_thinking_model()})
        try:
            new_goal_data = json.loads(creative_goal_response)
            if (
                isinstance(new_goal_data, dict) and
                "name" in new_goal_data and
                "description" in new_goal_data and
                "tier" in new_goal_data
            ):
                # Don't add if duplicate by name/desc/tier
                is_duplicate = any(
                    g.get("name") == new_goal_data["name"] and
                    g.get("description", "") == new_goal_data["description"] and
                    g.get("tier") == new_goal_data["tier"]
                    for g in goals
                )
                # Also skip if it suggests the same contradiction goal
                if (
                    not is_duplicate and
                    "contradiction" not in new_goal_data["name"].lower() and
                    "contradiction" not in new_goal_data["description"].lower()
                ):
                    new_goal = {
                        "name": new_goal_data["name"],
                        "tier": new_goal_data["tier"],
                        "description": new_goal_data["description"],
                        "status": "active",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "emotional_intensity": 0.5,
                        "history": [
                            {"event": "created", "timestamp": datetime.now(timezone.utc).isoformat()}
                        ]
                    }
                    goals.append(new_goal)
                    save_json(GOALS_FILE, goals)
                    update_working_memory(f"🌱 Created new novel goal: {new_goal['name']}")
        except Exception as e:
            update_working_memory(f"⚠️ Failed to create novel goal: {e}")

        self_model_maintenance_cycle()
        maybe_complete_goals()
        return "✅ Self-belief reflection complete."

    except Exception as e:
        log_error(f"reflect_on_self_beliefs ERROR: {e}")
        update_working_memory("❌ Reflection process failed.")
        return "❌ Reflection error."