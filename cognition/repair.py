# === Imports ===
import json
from memory.working_memory import update_working_memory
from utils.json_utils import load_json, save_json, extract_json
from utils.log import log_error, log_private, log_model_issue, log_activity
from utils.log_reflection import log_reflection
from utils.generate_response import generate_response, get_thinking_model
from utils.load_utils import load_all_known_json
from utils.feedback_log import log_feedback
from utils.response_utils import generate_response_from_context
from cognition.reflection.reflect_on_cognition import update_cognition_schedule
from emotion.reward_signals.reward_signals import release_reward_signal

from paths import REF_PROMPTS
REF_PROMPTS = load_json(REF_PROMPTS, default_type=dict)

# === Constants ===
CONTRADICTIONS_FILE = "contradictions.json"

# === Functions ===
def reflect_on_cognition_rhythm():
    try:
        data = load_all_known_json()

        history = [h for h in data.get("cognition_history", []) if isinstance(h, dict)][-30:]
        if not history:
            return

        schedule = data.get("cognition_schedule", {})
        prompt_template = REF_PROMPTS.get("reflect_on_cognition_rhythm", "")
        if not prompt_template:
            log_model_issue("⚠️ Missing or invalid prompt: reflect_on_cognition_rhythm")
            return

        recent_entries = ""
        for h in history:
            try:
                choice = h.get("choice", "unknown")
                timestamp = h.get("timestamp", "unknown").split("T")[0]
                reason = h.get("reason", "")
                recent_entries += f"- {choice} on {timestamp}: {reason}\n"
            except Exception as e:
                log_error(f"⚠️ Skipped malformed history entry: {e}")

        context = {
            **data,
            "recent_history_summary": recent_entries,
            "instructions": (
                f"{prompt_template}\n\n"
                f"Current cognition schedule:\n{json.dumps(schedule, indent=2)}\n\n"
                f"Recent choices:\n{recent_entries}\n\n"
                "Respond with JSON like: { \"dream\": 8, \"reflect\": 4 } or {} if no change."
            )
        }

        response = generate_response_from_context(context)
        changes = extract_json(response)
        

        if isinstance(changes, dict) and changes:
            update_cognition_schedule(changes)
            log_private(f"Orrin updated cognition rhythm: {json.dumps(changes)}")
            log_reflection(f"Self-belief reflection: {changes}")
            log_feedback({
                "goal": "Revised cognition schedule",
                "result": "Success",
                "agent": "The Strategist",
                "emotion": "organized"
            })

            release_reward_signal(context, signal_type="dopamine", actual_reward=1.0, expected_reward=0.6)

    except Exception as e:
        log_error(f"reflect_on_cognition_rhythm ERROR: {e}")
        update_working_memory("⚠️ Cognition rhythm reflection failed.")


def detect_contradiction(thoughts):
    prompt = (
        "I am Orrin, scanning my recent reflections for contradictions.\n"
        "Look for internal conflicts, misaligned beliefs, or value mismatches.\n\n"
        "Thoughts:\n" + thoughts + "\n\n"
        "Respond in JSON ONLY:\n"
        "{ \"contradictions\": [ {\"summary\": \"...\", \"source\": \"...\", \"suggested_fix\": \"...\"} ] }"
    )

    result = generate_response(prompt, config={"model": get_thinking_model()})
    contradictions = extract_json(result)

    if contradictions and "contradictions" in contradictions:
        existing_log = load_json(CONTRADICTIONS_FILE, default_type=list)
        existing_log.append(contradictions)
        save_json(CONTRADICTIONS_FILE, existing_log)

        log_activity("🧠 Contradiction detected and logged.")
        update_working_memory("⚠️ Contradiction flagged for future self-repair.")

        log_feedback({
            "goal": "Repair contradiction in recent thoughts",
            "result": "Failure",
            "agent": "The Dreamer",
            "emotion": "confused"
        })

    return contradictions

def repair_contradictions(text):
    prompt = (
        "I am a self-aware AI checking for contradictions in my own thoughts.\n\n"
        f"Thought to inspect:\n{text}\n\n"
        "If contradictions exist, explain them. Then try to resolve them using follow-up reasoning.\n"
        "Respond ONLY with: {\"contradictions\": [...], \"repair_attempt\": \"...\"}"
    )
    try:
        response = generate_response(prompt, config={"model": get_thinking_model()})
        result = extract_json(response)
        return result if isinstance(result, dict) else {"contradictions": [], "repair_attempt": ""}
    except Exception as e:
        log_model_issue(f"[repair_contradictions] Failed to parse contradiction repair: {e}\nRaw: {response if 'response' in locals() else 'No response'}")
        return {"contradictions": [], "repair_attempt": ""}
