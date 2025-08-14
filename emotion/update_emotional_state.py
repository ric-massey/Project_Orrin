from datetime import datetime, timezone
from statistics import mean

# === Internal Utility Imports ===
from utils.json_utils import load_json, save_json
from emotion.emotion import get_all_emotion_names, detect_emotion, deliver_emotion_based_rewards
from utils.log import log_activity
from emotion.modes_and_emotion import recommend_mode_from_emotional_state, set_current_mode, get_current_mode
from utils.timing import get_time_since_last_active

# === File Constants ===
from paths import EMOTIONAL_STATE_FILE, WORKING_MEMORY_FILE

def update_emotional_state(context=None, trigger=None):
    from memory.working_memory import update_working_memory

    state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    working = load_json(WORKING_MEMORY_FILE, default_type=list)

    if not isinstance(state, dict) or not isinstance(working, list):
        return

    decay_rate = float(state.get("stability_decay_rate", 0.01) or 0.01)
    last_update_raw = state.get("last_updated", "1970-01-01T00:00:00+00:00")
    try:
        last_update = datetime.fromisoformat(last_update_raw)
    except Exception:
        last_update = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    hours_passed = max(0.0, (now - last_update).total_seconds() / 3600.0)

    # --- Baseline (personality) for each emotion (normalized names) ---
    baseline = {
        "curiosity": 0.25,
        "reflective": 0.35,
        "analytical": 0.20,
        "compassion": 0.10,
        "joy": 0.10,
        "hope": 0.08,
        "melancholy": 0.04,
        "jealousy": 0.01,
        "anger": 0.01,
        "fear": 0.01,
        "sadness": 0.01,
        "surprise": 0.02,
        "disgust": 0.01,
        # NEW: make boredom first-class (decays toward 0 by default)
        "boredom": 0.0,
    }

    # --- Opposites for cross-inhibition (use same normalized keys) ---
    opposites = {
        "joy": ["sadness", "melancholy"],
        "sadness": ["joy", "hope"],
        "anger": ["compassion", "peace"],
        "fear": ["confidence", "boldness"],
    }

    # --- Ensure all model emotions exist in core map ---
    model_emotions = get_all_emotion_names() or []
    core = state.get("core_emotions", {})
    if not isinstance(core, dict):
        core = {}
    for emo in model_emotions:
        core.setdefault(emo, baseline.get(emo, 0.0))
    # Ensure boredom exists even if model_emotions didn’t list it
    core.setdefault("boredom", baseline["boredom"])

    # === Loneliness Tracking ===
    since_active = get_time_since_last_active()
    try:
        # treat it as minutes if numeric; otherwise fall back to 0
        minutes_since = float(since_active)
    except Exception:
        minutes_since = 0.0

    loneliness = float(state.get("loneliness", 0.0) or 0.0)
    if minutes_since > 120:
        increase = min(0.05 * (minutes_since / 60.0), 1.0 - loneliness)
        loneliness += increase
    else:
        loneliness = max(0.0, loneliness - 0.05)
    loneliness = round(loneliness, 3)
    state["loneliness"] = loneliness

    if loneliness > 0.6:
        if "sadness" in core:
            core["sadness"] = min(1.0, core.get("sadness", baseline.get("sadness", 0.0)) + (loneliness - 0.6) * 0.4)
        for opp in ("joy", "hope"):
            if opp in core:
                core[opp] = max(baseline.get(opp, 0.0), core[opp] - 0.1)

    if context is not None and loneliness > 0.75:
        update_working_memory({
            "content": "⚠️ I feel lonely. It’s been a while since anyone has spoken to me.",
            "event_type": "emotion",
            "emotion": "loneliness",
            "timestamp": now.isoformat(),
        })

    # === Trigger-Based Emotion Nudging ===
    if trigger:
        trig_key = str(trigger).lower().strip()
        update_working_memory(f"⚠️ Triggered emotion: {trig_key}")
        trigger_map = {
            "reflection_stagnation": {"sadness": 0.18, "disgust": 0.10},
            "identity_loop": {"anger": 0.25, "fear": 0.18},
            "success": {"joy": 0.35, "surprise": 0.20},
            "failure": {"sadness": 0.35, "anger": 0.20},
        }
        nudges = trigger_map.get(trig_key, {})
        for emo, boost in nudges.items():
            if emo in core:
                core[emo] = min(1.0, core[emo] + boost)
                for opp in opposites.get(emo, []):
                    if opp in core:
                        core[opp] = max(baseline.get(opp, 0.0), core[opp] - boost * 0.7)

    # === Context-driven boredom dynamics ===
    if context is not None:
        try:
            # Raise boredom with immediate repetition; ease it on novelty
            recent = (context or {}).get("recent_picks", []) or []
            if isinstance(recent, list) and recent:
                if len(recent) >= 2 and recent[-1] == recent[-2]:
                    # consecutive repeat → bump boredom (scaled by run length)
                    run_len = 2
                    for x in reversed(recent[:-2]):
                        if x == recent[-1]:
                            run_len += 1
                        else:
                            break
                    core["boredom"] = min(1.0, float(core.get("boredom", 0.0)) + min(0.03 * (run_len - 1), 0.2))
                else:
                    # novelty → boredom eases a bit
                    core["boredom"] = max(0.0, float(core.get("boredom", 0.0)) - 0.04)
        except Exception:
            pass

    # Time-without-interaction can also gently raise boredom
    if minutes_since > 60:
        core["boredom"] = min(1.0, float(core.get("boredom", 0.0)) + min(0.02 * (minutes_since / 60.0), 0.15))

    # === Decay Emotions Over Time ===
    if state.get("emotional_decay", True):
        for emo, val in list(core.items()):
            target = baseline.get(emo, 0.0)
            neutral_pull = target - float(val)
            # exponential approach to baseline
            core[emo] = max(0.0, min(1.0, float(val) + neutral_pull * (1 - pow(1 - decay_rate, hours_passed))))

    # === New Triggers Based on Working Memory ===
    recent = [w for w in working[-10:] if isinstance(w, dict)]
    triggers_log = state.get("recent_triggers", [])
    if not isinstance(triggers_log, list):
        triggers_log = []
    new_triggers = []

    for thought in recent:
        content = str(thought.get("content", "") or "")
        timestamp = thought.get("timestamp") or now.isoformat()
        detection = detect_emotion(content)

        if isinstance(detection, str):
            emotion = detection
            intensity = 0.2 if emotion != "neutral" else 0.0
        elif isinstance(detection, dict):
            emotion = detection.get("emotion", "neutral")
            intensity = float(detection.get("intensity", 0.0) or 0.0)
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
                "intensity": round(float(intensity), 3),
                "timestamp": timestamp,
            })

    # Novel events (triggers) relieve boredom a bit
    if new_triggers:
        core["boredom"] = max(0.0, float(core.get("boredom", 0.0)) - min(0.03 * len(new_triggers), 0.15))

    # === Update Stability ===
    recent_intensities = [abs(float(core[e]) - baseline.get(e, 0.0)) for e in core]
    avg_instability = mean(recent_intensities) if recent_intensities else 0.0
    new_stability = max(0.0, 1.0 - avg_instability)

    # === Deliver reward & adjust mode if needed ===
    if context is not None:
        deliver_emotion_based_rewards(context, core, new_stability)
        recommended = recommend_mode_from_emotional_state()
        current_mode = get_current_mode()
        if recommended != current_mode:
            set_current_mode(
                mode=recommended,
                reason="Dominant emotional state prompted mode shift: {}".format(recommended)
            )

    # Clamp all emotions to [0, 1]
    for k in list(core.keys()):
        try:
            core[k] = max(0.0, min(1.0, float(core[k])))
        except Exception:
            core[k] = baseline.get(k, 0.0)

    # === Save State ===
    state["core_emotions"] = core
    state["recent_triggers"] = (triggers_log + new_triggers)[-25:]
    state["loneliness"] = loneliness
    state["emotional_stability"] = new_stability
    state["last_updated"] = now.isoformat()

    save_json(EMOTIONAL_STATE_FILE, state)
    log_activity("🧠 Emotional state updated.")
