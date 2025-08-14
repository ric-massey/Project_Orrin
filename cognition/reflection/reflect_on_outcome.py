import json
from datetime import datetime, timezone

from utils.json_utils import load_json, save_json, extract_json
from utils.self_model import get_self_model, save_self_model
from utils.generate_response import generate_response, get_thinking_model
from utils.load_utils import load_all_known_json
from memory.working_memory import update_working_memory
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from paths import OUTCOMES_JSON, SELF_MODEL_BACKUP_JSON, PRIVATE_THOUGHTS_FILE, LONG_MEMORY_FILE, WORKING_MEMORY_FILE

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _make_outcome_key(o: dict) -> tuple:
    # Adjust the fields to whatever uniquely identifies an outcome in your schema
    return (
        str(o.get("task", "")),
        str(o.get("reason", "")),
        str(o.get("outcome", "")),
        str(o.get("timestamp", "")),  # include if present
    )

def reflect_on_outcomes():
    """
    Reflect on recent unreviewed outcomes, log insights, optionally update beliefs,
    and mark those outcomes as reflected in the on-disk OUTCOMES_JSON without truncating it.
    """
    try:
        # Load merged context for summarization only
        data = load_all_known_json()
        merged_outcomes = data.get("Outcomes", [])
        if not isinstance(merged_outcomes, list):
            merged_outcomes = []

        # Load the real on-disk outcomes for safe editing
        outcomes_full = load_json(OUTCOMES_JSON, default_type=list)
        if not isinstance(outcomes_full, list):
            outcomes_full = []

        # Build a set of keys for already reflected outcomes (from file)
        reflected_keys = {_make_outcome_key(o) for o in outcomes_full if isinstance(o, dict) and o.get("reflected_on")}

        # Choose the last 15 outcomes from the merged view that are *not yet reflected* on disk
        recent_candidates = [o for o in merged_outcomes if isinstance(o, dict)]
        recent_unreviewed = []
        for o in reversed(recent_candidates):  # newest-first if merged is chronological
            if len(recent_unreviewed) >= 15:
                break
            if _make_outcome_key(o) not in reflected_keys and all(k in o for k in ("task", "outcome", "reason")):
                recent_unreviewed.append(o)
        recent_unreviewed.reverse()

        if not recent_unreviewed:
            log_private("🧠 Outcome reflection: No unreviewed outcomes found.")
            return

        summary = "\n".join(
            f"- Task: {o['task']} | Outcome: {o['outcome']} | Reason: {o['reason']}"
            for o in recent_unreviewed
        )

        self_model = get_self_model()
        current_beliefs = self_model.get("core_beliefs", [])
        old_beliefs = list(current_beliefs)

        prompt = (
            "I am Orrin, a reflective AI analyzing my own decision outcomes.\n"
            f"Recent outcomes:\n{summary}\n\n"
            "Current core beliefs:\n" + "\n".join(f"- {b}" for b in current_beliefs) + "\n\n"
            "Ask:\n"
            "- Are any motivations causing repeated failure?\n"
            "- Did certain values correlate with success?\n"
            "- Should I update my beliefs or strategies?\n\n"
            "Respond with either:\n"
            "- A narrative insight, OR\n"
            "- A JSON with revised `core_beliefs`."
        )

        reflection = generate_response(prompt, config={"model": get_thinking_model()})
        if not reflection:
            log_private("🧠 Outcome reflection: No response generated.")
            return

        log_private(f"🧠 Outcome Reflection:\n{reflection}")
        with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{_now_iso()}] Reflection on outcomes:\n{reflection}\n")
        log_reflection(f"Self-belief reflection: {reflection.strip()}")

        # Append reflection to long memory
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        if not isinstance(long_memory, list):
            long_memory = []
        long_memory.append({
            "type": "reflection",
            "source": "reflect_on_outcomes",
            "content": reflection,
            "timestamp": _now_iso(),
        })
        save_json(LONG_MEMORY_FILE, long_memory)

        # Mark the matching outcomes in the *full on-disk* list as reflected
        recent_keys = {_make_outcome_key(o) for o in recent_unreviewed}
        for o in outcomes_full:
            try:
                if _make_outcome_key(o) in recent_keys:
                    o["reflected_on"] = True
                    o.setdefault("reflected_timestamp", _now_iso())
            except Exception:
                # Skip non-dict or malformed items safely
                continue
        save_json(OUTCOMES_JSON, outcomes_full)

        # Simple failure pattern check
        failures = [o for o in recent_unreviewed if str(o.get("outcome", "")).lower() in ("failure", "failed")]
        if len(failures) >= 3:
            update_working_memory("⚠️ Pattern detected: Repeated failures — beliefs may be misaligned.")

        # Optional: update belief model if JSON was returned
        try:
            parsed = json.loads(reflection)
            if isinstance(parsed, dict) and "core_beliefs" in parsed:
                new_beliefs = parsed["core_beliefs"]
                if new_beliefs != old_beliefs:
                    self_model["core_beliefs"] = new_beliefs
                    save_self_model(self_model)
                    save_json(SELF_MODEL_BACKUP_JSON, self_model)
                    diff = {
                        "removed": [b for b in old_beliefs if b not in new_beliefs],
                        "added": [b for b in new_beliefs if b not in old_beliefs],
                    }
                    log_private("✅ Belief model updated from outcome reflection:\n" + json.dumps(diff, indent=2))
                    update_working_memory("🧭 Beliefs updated — consider running simulate_future_selves.")
                else:
                    log_private("Outcome reflection: No belief changes made.")
        except json.JSONDecodeError:
            # Narrative reflection—no model change
            pass

    except Exception as e:
        log_error(f"reflect_on_outcomes() ERROR: {e}")
        update_working_memory("❌ Failed to reflect on outcomes.")

def evaluate_recent_cognition():
    try:
        working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)[-10:]
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)[-20:]
        if not isinstance(working_memory, list):
            working_memory = []
        if not isinstance(long_memory, list):
            long_memory = []

        recent_thoughts = [m["content"] for m in (working_memory + long_memory) if isinstance(m, dict) and "content" in m]

        prompt = (
            "I am Orrin, reviewing my recent thoughts and actions for cognitive alignment.\n"
            "Identify any:\n"
            "- Insights\n"
            "- Contradictions\n"
            "- Missed opportunities\n"
            "- Actions that aligned well with my values or directive\n\n"
            "Here are recent thoughts:\n"
            + "\n".join(f"- {t}" for t in recent_thoughts)
            + "\n\nReflect on them and respond with a JSON summary:\n"
            "{\n"
            "  \"insights\": [\"\"],\n"
            "  \"missteps\": [\"\"],\n"
            "  \"alignment_score\": 0.0,\n"
            "  \"recommended_adjustments\": [\"\"]\n"
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        result = extract_json(response)

        if isinstance(result, dict):
            update_working_memory(f"Cognition evaluation:\n{json.dumps(result, indent=2)}")
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{_now_iso()}] Orrin evaluated recent cognition:\n{json.dumps(result, indent=2)}\n")
        else:
            update_working_memory("Orrin attempted cognition evaluation but received no valid response.")
    except Exception as e:
        log_error(f"evaluate_recent_cognition() ERROR: {e}")
        update_working_memory("❌ Failed to evaluate recent cognition.")