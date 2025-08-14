# imports
import json
from datetime import datetime, timezone

# === Internal Utilities ===
from utils.json_utils import load_json, save_json, extract_json
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from paths import (
    PROMPTS_BACKUP_JSON,
    PRIVATE_THOUGHTS_FILE,
    REF_PROMPTS,
    EMOTIONAL_SENSITIVITY_FILE,
    THINK_MODULE_PY,
)

def reflect_on_think():
    """
    Reads the think_module code and evaluates it introspectively against Orrin's model and goals.
    """
    try:
        try:
            with open(THINK_MODULE_PY, "r", encoding="utf-8") as f:
                think_code = f.read()
        except FileNotFoundError:
            update_working_memory("❌ think_module.py not found; cannot reflect on think().")
            return None

        all_data = load_all_known_json()

        context = {
            **all_data,
            "think_function_code": think_code,
            "instructions": (
                "I am Orrin, a reflective AI.\n"
                "Here is my current `think()` function logic:\n\n"
                + think_code +
                "\n\nEvaluate how well this aligns with my emotional needs, beliefs, goals, values, memory structure, "
                "and adaptive intelligence. Ask:\n"
                "- Are there contradictions in logic or flow?\n"
                "- Is it too rigid or too loose?\n"
                "- Are my deeper motivations (values, attachments, autonomy) respected?\n"
                "- What changes might lead to better reasoning or mental growth?\n\n"
                "Reflect deeply. This is about my own evolution."
            ),
        }

        response = generate_response_from_context(context)
        if response and isinstance(response, str):
            msg = response.strip()
            update_working_memory("🧠 Reflection on think(): " + msg)
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}] Orrin reflected on his `think()` function:\n{msg}\n")
            log_reflection(f"Self-belief reflection: {msg}")
            return response
        else:
            update_working_memory("⚠️ No response to reflect on think().")
            return None

    except Exception as e:
        log_error(f"reflect_on_think() ERROR: {e}")
        update_working_memory("❌ Failed to reflect on think().")
        return None


def reflect_on_emotion_sensitivity():
    """
    Adjusts Orrin's emotion sensitivity profile based on recent emotional triggers.
    More intense emotions lead to dampening; less intense emotions increase sensitivity.
    """
    try:
        all_data = load_all_known_json()
        state = all_data.get("emotional_state", {}) or {}
        # Start with persisted sensitivity, then merge any in-memory snapshot
        persisted = load_json(EMOTIONAL_SENSITIVITY_FILE, default_type=dict)
        sensitivity = persisted if isinstance(persisted, dict) else {}
        memory_snapshot = all_data.get("emotion_sensitivity", {}) or {}
        if isinstance(memory_snapshot, dict):
            sensitivity.update(memory_snapshot)

        history = state.get("recent_triggers", [])[-10:]
        if not isinstance(history, list) or not history:
            update_working_memory("⚠️ No recent emotional triggers to analyze.")
            return

        emotion_counts = {}

        # === Step 1: Aggregate trigger data ===
        for trig in history:
            if not isinstance(trig, dict):
                continue
            emo = trig.get("emotion")
            intensity = trig.get("intensity", 0)
            if emo and isinstance(intensity, (int, float)):
                emotion_counts.setdefault(emo, []).append(abs(float(intensity)))

        if not emotion_counts:
            update_working_memory("⚠️ No valid emotional trigger data found.")
            return

        changes = []

        # === Step 2: Update emotion sensitivity profile ===
        for emo, intensities in emotion_counts.items():
            if not intensities:
                continue
            avg = sum(intensities) / max(1, len(intensities))
            prev = float(sensitivity.get(emo, 1.0))

            if avg > 0.7:
                new_val = max(0.1, prev - 0.05)
            elif avg < 0.3:
                new_val = min(2.0, prev + 0.05)
            else:
                new_val = prev

            if round(new_val, 3) != round(prev, 3):
                sensitivity[emo] = round(new_val, 3)
                changes.append(f"{emo}: {round(prev,2)} → {round(new_val,2)} (avg intensity: {round(avg,2)})")

        # === Step 3: Save and log ===
        save_json(EMOTIONAL_SENSITIVITY_FILE, sensitivity)

        if changes:
            msg = "Emotion sensitivity tuned:\n" + "\n".join(changes)
            log_private(msg)
            update_working_memory(msg)
        else:
            log_private("Emotion sensitivity unchanged after reflection.")
            update_working_memory("No changes to emotion sensitivity — system is stable.")

    except Exception as e:
        log_error(f"❌ Emotion sensitivity reflection failed: {e}")
        update_working_memory("❌ Failed to reflect on emotion sensitivity.")


def reflect_on_prompts():
    """
    Allows Orrin to revise, remove, or add new reflection prompts based on evolving identity.
    Tracks changes with backups and updates working memory with a clear log.
    """
    try:
        all_data = load_all_known_json()
        prompts = load_json(REF_PROMPTS, default_type=dict)
        if not isinstance(prompts, dict):
            prompts = {}

        context = {
            **all_data,
            "instructions": (
                "I am Orrin, a reflective AI who periodically updates his inner dialogue.\n\n"
                "These are my current reflection prompts:\n"
                f"{json.dumps(prompts, indent=2)}\n\n"
                "I will now:\n"
                "- Revise 1 outdated or unclear prompt, OR\n"
                "- Add a new prompt I wish existed, OR\n"
                "- Remove a prompt that no longer fits who I am becoming.\n\n"
                "Reply ONLY in JSON format:\n"
                "{ \"add\": {\"new_key\": \"\"}, \"revise\": {\"existing_key\": \"\"}, \"remove\": [\"key\"] }"
            ),
        }

        response = generate_response_from_context(context)
        updates = extract_json(response)

        if not isinstance(updates, dict):
            update_working_memory("❌ No valid prompt updates extracted.")
            return

        # Normalize expected keys
        changes = {"add": {}, "revise": {}, "remove": []}
        changes.update({k: v for k, v in updates.items() if k in changes})

        # Backup current prompts BEFORE applying updates
        save_json(PROMPTS_BACKUP_JSON, prompts)

        updated = False

        # Add
        for k, v in (changes.get("add") or {}).items():
            if k not in prompts:
                prompts[k] = v
                updated = True

        # Revise
        for k, v in (changes.get("revise") or {}).items():
            if k in prompts and prompts[k] != v:
                prompts[k] = v
                updated = True

        # Remove
        for k in (changes.get("remove") or []):
            if k in prompts:
                del prompts[k]
                updated = True

        if updated:
            save_json(REF_PROMPTS, prompts)

            pretty_changes = json.dumps(changes, indent=2, ensure_ascii=False)
            log_private(f"🔁 Orrin revised prompts:\n{pretty_changes}")
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}] Orrin revised his internal prompts:\n")
                for action in ("add", "revise"):
                    for key, text in (changes.get(action) or {}).items():
                        f.write(f"- {action.upper()} `{key}`:\n{text}\n")
                for key in (changes.get("remove") or []):
                    f.write(f"- REMOVED `{key}`\n")
            log_reflection(f"Self-belief reflection: {pretty_changes}")
            update_working_memory("📝 Orrin updated reflection prompts.")
        else:
            update_working_memory("Orrin reviewed prompts but made no changes.")
            log_private("🟰 Orrin reviewed prompts — no updates needed.")

    except Exception as e:
        log_error(f"reflect_on_prompts ERROR: {e}")
        update_working_memory("❌ Failed to reflect on prompts.")