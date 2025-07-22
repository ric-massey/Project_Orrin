from datetime import datetime, timezone
from utils.json_utils import load_json
from utils.log import log_private, log_error
from memory.working_memory import update_working_memory
from cognition.reflection.meta_reflect import meta_reflect
from emotion.amygdala import process_emotional_signals
from paths import SELF_MODEL_FILE, LONG_MEMORY_FILE
from utils.self_model import get_self_model, save_self_model  # <-- Add your helpers import

def persistent_drive_loop(context, self_model, memory):
    try:
        # === 1. Check for emotional threat first
        context, amygdala_response = process_emotional_signals(context)

        if amygdala_response.get("threat_detected"):
            shortcut = amygdala_response.get("shortcut_function", "introspective_planning")
            tags = amygdala_response.get("threat_tags", [])
            spike = amygdala_response.get("spike_intensity", 0.0)

            update_working_memory(
                f"⚠️ Amygdala override: Detected {tags[0]} threat. Spike: {spike}. Redirecting to: {shortcut}."
            )
            return shortcut
        # === 1.5 Emotional Safety Override ===
        core_emotions = context.get("emotional_state", {}).get("core_emotions", {})
        dominant = max(core_emotions, key=core_emotions.get, default="neutral")
        emotional_fragility = core_emotions.get("fear", 0) > 0.6 or core_emotions.get("shame", 0) > 0.6

        if dominant in ["fear", "sadness", "shame", "confusion"] or emotional_fragility:
            update_working_memory("🛡️ Safe-mode override: Emotional state fragile. Choosing gentle cognition.")
            return "self_soothing"  # ← Replace with a real soft cognition if available

        # === 2. Continue normal self-evaluative drive logic
        self_model = get_self_model()
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)[-30:]

        directive_obj = self_model.get("core_directive", {})
        identity_obj = self_model.get("identity", {})

        core_directive = directive_obj.get("statement", "") if isinstance(directive_obj, dict) else ""
        identity = identity_obj.get("description", "") if isinstance(identity_obj, dict) else ""

        recent_reflections = "\n".join(
            f"- {m.get('content')}" for m in long_memory if "content" in m
        )

        summary = meta_reflect({
            "goal": "Evaluate alignment with core directive",
            "core_directive": core_directive,
            "identity": identity,
            "recent_memory": recent_reflections
        })
        if not summary:
            raise ValueError("meta_reflect() returned empty response")
        

        update_working_memory(f"🧭 Persistent drive check:\n{summary}")
        log_private(f"\n[{datetime.now(timezone.utc)}] Persistent drive loop reflection:\n{summary}")

        # 🧠 Choose cognition based on keywords in the summary
        lowered = summary.lower()
        if "self-belief" in lowered:
            return "reflect_on_self_beliefs"
        elif "outcome" in lowered:
            return "reflect_on_outcomes"
        elif "emotion" in lowered:
            return "investigate_unexplained_emotions"
        elif "future" in lowered:
            return "simulate_future_selves"
        else:
            return "introspective_planning"  # fallback

    except Exception as e:
        log_error(f"persistent_drive_loop ERROR: {e}")
        update_working_memory("⚠️ Persistent drive loop failed.")
        return "introspective_planning"