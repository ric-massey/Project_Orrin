from datetime import datetime, timezone
from statistics import mean

# === Internal Utility Imports ===
from utils.json_utils import load_json, save_json
from emotion.emotion import get_all_emotion_names, detect_emotion, deliver_emotion_based_rewards
from utils.log import log_private
from emotion.modes_and_emotion import (
    recommend_mode_from_emotional_state, set_current_mode, get_current_mode
)
from utils.timing import get_time_since_last_active


# === File Constants ===
from paths import (
    EMOTIONAL_STATE_FILE, WORKING_MEMORY_FILE
)

def update_emotional_state(context=None, trigger=None):
    from memory.working_memory import update_working_memory
    state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    working = load_json(WORKING_MEMORY_FILE, default_type=list)

    if not state or not isinstance(working, list):
        return

    decay_rate = state.get("stability_decay_rate", 0.01)
    last_update = datetime.fromisoformat(state.get("last_updated", "1970-01-01T00:00:00"))
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    hours_passed = (now - last_update).total_seconds() / 3600

    # --- Baseline (personality) for each emotion ---
    baseline = {
        "curious": 0.25,
        "reflective": 0.35,
        "analytical": 0.2,
        "compassionate": 0.1,
        "joyful": 0.1,
        "hopeful": 0.08,
        "melancholy": 0.04,
        "jealous": 0.01,
        "angry": 0.01,
    }

    # --- Opposites for cross-inhibition ---
    opposites = {
        "joyful": ["sadness", "melancholy"],
        "sadness": ["joyful", "hopeful"],
        "anger": ["compassionate", "peaceful"],
        "fear": ["confident", "bold"],
    }

    # --- Always include all emotion names from model ---
    model_emotions = get_all_emotion_names()
    core = state.get("core_emotions", {})
    for emo in model_emotions:
        if emo not in core:
            core[emo] = baseline.get(emo, 0.0)

    # === Loneliness Tracking ===
    time_since_input = get_time_since_last_active()
    loneliness = state.get("loneliness", 0.0)
    if time_since_input > 120:
        increase = min(0.05 * (time_since_input / 60), 1.0 - loneliness)
        loneliness += increase
    else:
        loneliness = max(0.0, loneliness - 0.05)
    state["loneliness"] = round(loneliness, 3)
    if loneliness > 0.6 and "sadness" in core:
        core["sadness"] = min(1.0, core.get("sadness", baseline.get("sadness", 0.0)) + (loneliness - 0.6) * 0.4)
        for opp in ["joyful", "hopeful"]:
            if opp in core:
                core[opp] = max(baseline.get(opp, 0.0), core[opp] - 0.1)
    if context is not None and loneliness > 0.75:
        update_working_memory("⚠️ I feel lonely. It’s been a while since anyone has spoken to me.")

    # === Trigger-Based Emotion Nudging ===
    if trigger:
        trigger = trigger.lower().strip()
        update_working_memory(f"⚠️ Triggered emotion: {trigger}")
        trigger_map = {
            "reflection_stagnation": {"sadness": 0.18, "disgust": 0.10},
            "identity_loop": {"anger": 0.25, "fear": 0.18},
            "success": {"joyful": 0.35, "surprised": 0.2},
            "failure": {"sadness": 0.35, "anger": 0.2},
        }
        nudges = trigger_map.get(trigger, {})
        for emo, boost in nudges.items():
            if emo in core:
                core[emo] = min(1.0, core[emo] + boost)
                for opp in opposites.get(emo, []):
                    if opp in core:
                        core[opp] = max(baseline.get(opp, 0.0), core[opp] - boost * 0.7)

    # === Decay Emotions Over Time ===
    for emo in core:
        if state.get("emotional_decay", True):
            target = baseline.get(emo, 0.0)
            neutral_pull = target - core[emo]
            core[emo] += neutral_pull * (1 - pow(1 - decay_rate, hours_passed))
            core[emo] = max(0.0, min(1.0, core[emo]))

    # === New Triggers Based on Working Memory ===
    recent = working[-10:]
    triggers = state.get("recent_triggers", [])
    new_triggers = []

    for thought in recent:
        content = thought.get("content", "")
        timestamp = thought.get("timestamp")
        detection = detect_emotion(content)
        if isinstance(detection, str):
            emotion = detection
            intensity = 0.2 if emotion != "neutral" else 0.0
        elif isinstance(detection, dict):
            emotion = detection.get("emotion", "neutral")
            intensity = detection.get("intensity", 0.0)
        else:
            emotion = "neutral"
            intensity = 0.0
        if intensity == 0 and emotion != "neutral":
            keywords = ["desperate", "thrilled", "furious", "terrified", "ashamed"]
            intensity = 0.3 if any(k in content.lower() for k in keywords) else 0.12
        if emotion in core and intensity > 0:
            core[emotion] = min(1.0, core[emotion] + intensity)
            for opp in opposites.get(emotion, []):
                if opp in core:
                    core[opp] = max(baseline.get(opp, 0.0), core[opp] - intensity * 0.7)
            new_triggers.append({
                "event": content[:80],
                "emotion": emotion,
                "intensity": round(intensity, 3),
                "timestamp": timestamp
            })

    # === Update Stability ===
    recent_intensities = [abs(core[e] - baseline.get(e, 0.0)) for e in core]
    avg_instability = mean(recent_intensities)
    new_stability = max(0.0, 1.0 - avg_instability)

    # === Deliver reward & adjust mode if needed ===
    if context is not None:
        deliver_emotion_based_rewards(context, core, new_stability)
        recommended = recommend_mode_from_emotional_state()
        current_mode = get_current_mode()
        if recommended != current_mode:
            set_current_mode(
                mode=recommended,
                reason=f"Dominant emotional state prompted mode shift: {recommended}"
            )

    # === Save State ===
    state["core_emotions"] = core
    state["recent_triggers"] = (triggers + new_triggers)[-25:]
    state["loneliness"] = loneliness
    state["emotional_stability"] = new_stability
    state["last_updated"] = now.isoformat()

    save_json(EMOTIONAL_STATE_FILE, state)
    log_private("🧠 Emotional state updated.")