# modes_and_emotion.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import json

from utils.json_utils import load_json, save_json
from utils.log import log_activity, log_error
from memory.working_memory import update_working_memory

from paths import MODE_FILE, PRIVATE_THOUGHTS_FILE, EMOTIONAL_STATE_FILE

def get_current_mode() -> str:
    try:
        data = load_json(MODE_FILE, default_type=dict)
        if not isinstance(data, dict):
            log_error(f"⚠️ {MODE_FILE} did not contain a dict. Returning 'unknown'.")
            return "unknown"
        return str(data.get("mode", "unknown"))
    except Exception as e:
        log_error(f"⚠️ Failed to load {MODE_FILE}: {e}")
        return "unknown"

def set_current_mode(mode: str, reason: Optional[str] = None) -> None:
    """
    Update Orrin's current operating mode with a reason.
    Logs transition and avoids duplicate mode setting.
    """
    try:
        previous = load_json(MODE_FILE, default_type=dict)
        if not isinstance(previous, dict):
            previous = {}
        old_mode = str(previous.get("mode", "unknown"))

        # No-op if unchanged
        if old_mode == mode:
            return

        if not reason:
            reason = f"Automatic adjustment detected internal condition for mode: {mode}"

        # Persist mode
        save_json(MODE_FILE, {"mode": mode})

        transition = {
            "from": old_mode,
            "to": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }

        # Append a human-readable trace
        with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[Mode Transition]\n{json.dumps(transition, indent=2)}\n")

        # Working-memory ping
        update_working_memory({
            "content": f"🔄 Orrin changed mode: {old_mode} → {mode}\nReason: {reason}",
            "event_type": "mode_change",
            "agent": "orrin",
            "importance": 2,
            "priority": 2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        log_activity(f"Mode change recorded: {old_mode} → {mode}")
    except Exception as e:
        log_error(f"⚠️ Failed to set mode to '{mode}': {e}")

def recommend_mode_from_emotional_state(min_intensity: float = 0.55, skip_neutral: bool = True) -> str:
    state: Dict[str, Any] = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    core: Dict[str, Any] = state.get("core_emotions", {}) if isinstance(state, dict) else {}

    if not isinstance(core, dict) or not core:
        return "adaptive"

    # Ensure we have numeric values
    numeric_core = {
        str(k): float(v) for k, v in core.items()
        if isinstance(v, (int, float))
    }
    if not numeric_core:
        return "adaptive"

    # Get top emotion and intensity
    emotion, intensity = max(numeric_core.items(), key=lambda x: x[1])

    if skip_neutral and emotion == "neutral":
        return "adaptive"
    if float(intensity) < float(min_intensity):
        return "adaptive"

    # Emotion → Mode mapping
    emotion_mode_map = {
        "joy": "creative",
        "anger": "critical",
        "sadness": "philosophical",
        "fear": "cautious",
        "disgust": "analytical",
        "surprise": "exploratory",
        # extend with your custom emotions if desired
    }

    return emotion_mode_map.get(emotion, "adaptive")

def emotion_driven_mode_shift() -> None:
    """
    Automatically adjusts Orrin's operating mode based on emotional state.
    """
    try:
        recommended_mode = recommend_mode_from_emotional_state()
        current_mode = get_current_mode()
        if recommended_mode != current_mode:
            set_current_mode(recommended_mode, reason="Emotional state shift detected.")
    except Exception as e:
        log_error(f"⚠️ Failed to shift mode from emotional state: {e}")