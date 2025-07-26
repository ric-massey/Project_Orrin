from datetime import datetime, timezone
import json
from utils.json_utils import (
    load_json,
    save_json
)
from utils.log import log_activity, log_error
from memory.working_memory import update_working_memory

# === Constants ===
from paths import(
    MODE_FILE, PRIVATE_THOUGHTS_FILE,
    EMOTIONAL_STATE_FILE 
)

def get_current_mode():
    try:
        data = load_json(MODE_FILE, default_type=dict)
        if not isinstance(data, dict):
            log_error("⚠️ current_mode.json was not a dict. Returning 'unknown'.")
            return "unknown"
        return data.get("mode", "unknown")
    except Exception as e:
        log_error(f"⚠️ Failed to load current_mode.json: {e}")
        return "unknown"

def set_current_mode(mode: str, reason: str = None):
    """
    Update Orrin's current operating mode with a reason.
    Logs transition and avoids duplicate mode setting.
    """
    try:
        previous = load_json(MODE_FILE, default_type=dict)
        if not isinstance(previous, dict):
            previous = {}
        old_mode = previous.get("mode", "unknown")

        if old_mode == mode:
            return  # No change

        if not reason:
            reason = f"Automatic adjustment detected internal condition for mode: {mode}"

        save_json(MODE_FILE, {"mode": mode})

        transition = {
            "from": old_mode,
            "to": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }

        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[Mode Transition]\n{json.dumps(transition, indent=2)}\n")

        update_working_memory({
            "content": f"🔄 Orrin changed mode: {old_mode} → {mode}\nReason: {reason}",
            "event_type": "mode_change",
            "agent": "orrin",
            "importance": 2,
            "priority": 2
        })
        log_activity(f"Mode change recorded: {old_mode} → {mode}")
    except Exception as e:
        log_error(f"⚠️ Failed to set mode: {e}")

def recommend_mode_from_emotional_state(min_intensity=0.55, skip_neutral=True):
    state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    core = state.get("core_emotions", {})

    if not isinstance(core, dict) or not core:
        return "adaptive"

    # Get top emotion and intensity
    dominant = max(core.items(), key=lambda x: x[1])
    emotion, intensity = dominant

    if skip_neutral and emotion == "neutral":
        return "adaptive"

    if intensity < min_intensity:
        return "adaptive"

    # Dynamic, emotion-to-mode mapping
    emotion_mode_map = {
        "joy": "creative",
        "anger": "critical",
        "sadness": "philosophical",
        "fear": "cautious",
        "disgust": "analytical",
        "surprise": "exploratory",
        # You can add more emotions here as they evolve
    }

    return emotion_mode_map.get(emotion, "adaptive")

def emotion_driven_mode_shift():
    """
    Automatically adjusts Orrin's operating mode based on emotional state.
    """
    try:
        recommended_mode = recommend_mode_from_emotional_state()
        current_mode = get_current_mode()
        if recommended_mode != current_mode:
            set_current_mode(recommended_mode, reason=f"Emotional state shift detected.")
    except Exception as e:
        log_error(f"⚠️ Failed to shift mode from emotional state: {e}")