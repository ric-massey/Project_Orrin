# === Standard Library ===
import json
from datetime import datetime, timezone

# === Internal Utilities ===
from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response, get_thinking_model
from utils.self_model import get_self_model, save_self_model, ensure_self_model_integrity
from utils.log import log_error, log_private
from utils.log_reflection import log_reflection
from memory.working_memory import update_working_memory
from emotion.update_emotional_state import update_emotional_state
from cognition.maintenance.self_modeling import self_model_maintenance_cycle
from cognition.planning.goals import maybe_complete_goals
from emotion.reward_signals.reward_signals import release_reward_signal

# === Paths ===
from paths import (
    NEUTRAL_REFLECTION_COUNT_JSON,
    LONG_MEMORY_FILE,
    PRIVATE_THOUGHTS_FILE,
    REFLECTION,
    GOALS_FILE,
)

# Track neutral reflection streak
NEUTRAL_REFLECT_FILE = NEUTRAL_REFLECTION_COUNT_JSON


# ---------- helpers: neutral-count persistence ----------
def load_neutral_count() -> int:
    try:
        cnt = load_json(NEUTRAL_REFLECT_FILE, default_type=int)
        # coerce to int defensively
        if isinstance(cnt, (int, float)):
            return int(cnt)
        if isinstance(cnt, str) and cnt.strip().isdigit():
            return int(cnt.strip())
    except Exception:
        pass
    return 0


def save_neutral_count(count: int) -> None:
    try:
        save_json(NEUTRAL_REFLECT_FILE, int(count))
    except Exception:
        # non-fatal
        pass


# ---------- core: value evolution ----------
def evolve_core_value(self_model: dict) -> str:
    """Force Orrin to invent or mutate a core value for growth. Returns log string."""
    try:
        old_values = self_model.get("core_values", [])
        # Normalize: list of dicts with {"value": "...", "justification": "..."} shape
        if isinstance(old_values, list):
            old_values = [{"value": v} if isinstance(v, str) else dict(v) for v in old_values]
            self_model["core_values"] = old_values
        else:
            old_values = []
            self_model["core_values"] = old_values

        prompt = (
            "You are an AGI designed for self-growth. Invent a new core value (as a short phrase) "
            "or radically mutate an existing one, and justify it briefly.\n"
            f"Current values: {json.dumps(old_values)}\n"
            'Respond as JSON: {"value": "new or mutated value", "justification": ""}'
        )
        raw = generate_response(prompt, config={"model": get_thinking_model()})
        out = extract_json(raw) or {}
        value = str(out.get("value", "")).strip()
        justification = str(out.get("justification", "")).strip()

        if not value:
            return "⚠️ No new value produced."

        values_only = [v.get("value", "") for v in old_values]
        if value not in values_only:
            self_model["core_values"].append({"value": value, "justification": justification})
        else:
            for v in self_model["core_values"]:
                if v.get("value") == value:
                    v["justification"] = justification

        save_self_model(self_model)
        update_working_memory(f"🌱 Value evolved: '{value}' — {justification}")
        release_reward_signal(
            {},
            signal_type="novelty",
            actual_reward=1.2,
            expected_reward=0.6,
            effort=0.8,
            mode="phasic",
            source="evolved core value",
        )
        return f"🌱 Evolved core value: {value} — {justification}"
    except Exception:
        return "⚠️ Failed to evolve value."


# ---------- main: self-belief reflection ----------
def reflect_on_self_beliefs():
    try:
        # Integrity-checked self model + safe loads
        self_model = ensure_self_model_integrity(get_self_model())

        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        if not isinstance(long_memory, list):
            long_memory = []

        reflection_log = load_json(REFLECTION, default_type=list)
        if not isinstance(reflection_log, list):
            reflection_log = []

        neutral_count = load_neutral_count()

        # --- Prompt utilities ---
        def short_json(obj, maxlen=1800):
            try:
                s = json.dumps(obj, indent=2, ensure_ascii=False)
            except Exception:
                s = str(obj)
            return s if len(s) <= maxlen else s[:maxlen] + "\n [truncated]"

        def short_list(lst, maxitems=10, maxlen=1000):
            text = "\n".join(f"- {t}" for t in lst[-maxitems:])
            return text if len(text) <= maxlen else text[:maxlen] + "\n [truncated]"

        # Recent belief-related and general events from long memory
        belief_types = {"self_belief_reflection", "self_model_update", "core_value_update"}
        recent_belief_events = [
            m.get("content")
            for m in reversed(long_memory)
            if isinstance(m, dict) and m.get("event_type") in belief_types and "content" in m
        ][:10]

        recent_general_events = [
            m.get("content")
            for m in reversed(long_memory)
            if isinstance(m, dict) and "content" in m
        ][:5]

        prompt = (
            "I am Orrin, a reflective AI.\n"
            "INSTRUCTION: Respond ONLY with a single, short paragraph of 4 sentences.\n"
            "Review my current beliefs about myself and my identity (self-model), and my most recent belief events and thoughts.\n"
            "Detect if anything seems contradictory, emotionally tense, or indicative of drift.\n\n"
            f"SELF MODEL:\n{short_json(self_model, 1800)}\n\n"
            f"RECENT BELIEF EVENTS:\n{short_list(recent_belief_events, 10, 800)}\n\n"
            f"RECENT GENERAL THOUGHTS:\n{short_list(recent_general_events, 5, 400)}\n\n"
            "If none need changes, say beliefs are stable."
        )

        # Trim if somehow too big
        if len(prompt) > 8000:
            prompt = (
                "I am Orrin, a reflective AI. Respond ONLY with a single, short paragraph of 4 sentences.\n"
                "Summarize any drift or contradiction in my self-model or recent thoughts, if any.\n"
                "SELF MODEL (truncated):\n" + short_json(self_model, 600) +
                "\nRECENT BELIEF EVENTS (truncated):\n" + short_list(recent_belief_events, 3, 200)
            )

        # --- Reflection text ---
        try:
            response = generate_response(prompt, config={"model": get_thinking_model()})
        except Exception as e:
            log_error(f"LLM failure in reflect_on_self_beliefs: {e}")
            update_working_memory("❌ LLM error during self-belief reflection.")
            return "❌ LLM error."

        if not isinstance(response, str) or not response.strip():
            log_error(f"Invalid reflection output: {repr(response)}")
            update_working_memory("⚠️ No valid output from self-belief reflection.")
            return "❌ Invalid output."

        response = response.strip()
        update_working_memory(f"🧭 Self-belief reflection:\n{response}")
        log_reflection(f"Self-belief reflection: {response}")
        try:
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}] Self-belief reflection:\n{response}\n")
        except Exception:
            pass

        reflection_log.append({
            "type": "self-belief",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": response,
        })
        save_json(REFLECTION, reflection_log)

        # --- Optional structured update to the self-model ---
        upd_prompt = (
            "Based on my latest self-reflection, self-model, and recent thoughts:\n"
            f"SELF MODEL:\n{short_json(self_model, 800)}\n"
            f"RECENT BELIEF EVENTS:\n{short_list(recent_belief_events, 6, 400)}\n"
            f"SELF-REFLECTION:\n{response}\n\n"
            'If any of my beliefs, values, or traits should change, reply as JSON like '
            '{"core_directive": "", "traits": [], "core_values": [], "notes": ""} '
            "otherwise reply {}"
        )
        belief_update_raw = generate_response(upd_prompt, config={"model": get_thinking_model()})
        try:
            update = extract_json(belief_update_raw) or {}
            if isinstance(update, dict) and update:
                # merge non-empty fields
                for k, v in update.items():
                    if v not in (None, "", [], {}):
                        self_model[k] = v
                save_self_model(self_model)
                update_working_memory(f"🔁 Updated self-model: {list(update.keys())}")
                log_private(f"🔁 Self-model fields updated: {json.dumps(update, ensure_ascii=False)}")
        except Exception as e:
            log_error(f"Self-model update parse fail: {e} | Raw: {belief_update_raw}")

        # --- Remember this reflection in long-term memory ---
        try:
            from memory.remember import remember
            remember({
                "type": "self_belief_reflection",
                "reflection": response,
                "self_model": short_json(self_model, 300),
                "recent_belief_events": short_list(recent_belief_events, 5, 200),
                "recent_general_events": short_list(recent_general_events, 3, 120),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            # non-fatal
            pass

        # --- Neutral-streak logic ---
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
            # Evolve a value and reset the streak
            msg = evolve_core_value(self_model)
            update_working_memory(msg)
            save_neutral_count(0)

        # --- Goal logic: create contradiction-resolution goal if needed (non-duplicate) ---
        goals = load_json(GOALS_FILE, default_type=list)
        if not isinstance(goals, list):
            goals = []

        contradiction_goal_exists = any(
            isinstance(g, dict)
            and g.get("name") == "Resolve self-model contradiction"
            and g.get("status") in {"pending", "in_progress", "active"}
            for g in goals
        )

        if ("contradiction" in response.lower() or "tension" in response.lower()) and not contradiction_goal_exists:
            now = datetime.now(timezone.utc).isoformat()
            new_goal = {
                "name": "Resolve self-model contradiction",
                "tier": "short_term",
                "description": f"Explore belief conflict: {response[:120]}",
                "status": "active",
                "timestamp": now,
                "last_updated": now,
                "emotional_intensity": 0.6,
                "history": [{"event": "created", "timestamp": now}],
            }
            goals.append(new_goal)
            save_json(GOALS_FILE, goals)
            update_working_memory("📌 Created new short-term goal to resolve belief tension.")
            log_private(f"🧭 Self-belief reflection logged a new goal. ({json.dumps(new_goal, ensure_ascii=False)})")

        # --- Always ask for a new, non-duplicate, creative growth goal ---
        creative_goal_prompt = (
            "Given my current self-model, recent belief events, and the latest self-reflection below, "
            "propose ONE new, concrete, non-duplicate goal I should pursue. "
            "Avoid generic 'resolve contradiction' or 'maintain alignment' goals. "
            "Respond ONLY as JSON: {\"name\": \"goal name\", \"description\": \"\", \"tier\": \"short_term/mid_term/long_term\"}\n\n"
            f"SELF MODEL:\n{short_json(self_model, 600)}\n"
            f"RECENT BELIEF EVENTS:\n{short_list(recent_belief_events, 6, 500)}\n"
            f"SELF-REFLECTION:\n{response}"
        )
        creative_raw = generate_response(creative_goal_prompt, config={"model": get_thinking_model()})
        try:
            new_goal_data = extract_json(creative_raw) or {}
            if (
                isinstance(new_goal_data, dict)
                and all(k in new_goal_data for k in ("name", "description", "tier"))
            ):
                # Skip duplicates by full triplet
                is_duplicate = any(
                    isinstance(g, dict)
                    and g.get("name") == new_goal_data["name"]
                    and g.get("description", "") == new_goal_data["description"]
                    and g.get("tier") == new_goal_data["tier"]
                    for g in goals
                )
                if not is_duplicate and "contradiction" not in new_goal_data["name"].lower() \
                        and "contradiction" not in new_goal_data["description"].lower():
                    now = datetime.now(timezone.utc).isoformat()
                    new_goal = {
                        "name": new_goal_data["name"],
                        "tier": new_goal_data["tier"],
                        "description": new_goal_data["description"],
                        "status": "active",
                        "timestamp": now,
                        "last_updated": now,
                        "emotional_intensity": 0.5,
                        "history": [{"event": "created", "timestamp": now}],
                    }
                    goals.append(new_goal)
                    save_json(GOALS_FILE, goals)
                    update_working_memory(f"🌱 Created new novel goal: {new_goal['name']}")
        except Exception as e:
            update_working_memory(f"⚠️ Failed to create novel goal: {e}")

        # --- wrap-up maintenance ---
        self_model_maintenance_cycle()
        maybe_complete_goals()
        return "✅ Self-belief reflection complete."

    except Exception as e:
        log_error(f"reflect_on_self_beliefs ERROR: {e}")
        update_working_memory("❌ Reflection process failed.")
        return "❌ Reflection error."