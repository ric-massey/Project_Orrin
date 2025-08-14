from datetime import datetime, timezone

from utils.json_utils import load_json, save_json
from utils.log import log_private, log_error, log_activity
from emotion.model import load_emotion_keywords
from emotion.reward_signals.reward_signals import release_reward_signal
from utils.self_model import get_self_model
from paths import (
    EMOTIONAL_STATE_FILE,
    WORKING_MEMORY_FILE,
    MODE_FILE,
    EMOTIONAL_SENSITIVITY_FILE, 
)

def decay_emotional_state():
    state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    if not state.get("emotional_decay", False):
        return

    decay_rate = float(state.get("stability_decay_rate", 0.01))
    core = dict(state.get("core_emotions", {}))

    for emotion, value in list(core.items()):
        drift = (0.5 - float(value)) * decay_rate  # pull toward neutrality
        core[emotion] = round(float(value) + drift, 4)

    state["core_emotions"] = core
    state["emotional_stability"] = round(
        max(0.0, float(state.get("emotional_stability", 1.0)) - decay_rate), 4
    )
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    save_json(EMOTIONAL_STATE_FILE, state)
    log_private("Emotional state decayed.")


def adjust_emotional_state(emotion: str, amount: float, reason: str = "", context=None):
    """Adjust a single core emotion with sensitivity, clamped to [0,1]."""
    if reason == "user_command":
        log_private(f"Refused to change emotion '{emotion}' due to direct user command.")
        return

    state_path = EMOTIONAL_STATE_FILE
    sensitivity_path = EMOTIONAL_SENSITIVITY_FILE

    state = load_json(state_path, default_type=dict)
    sensitivity = load_json(sensitivity_path, default_type=dict)
    core = dict(state.get("core_emotions", {}))

    sens = float(sensitivity.get(emotion, 1.0))
    scaled_amount = float(amount) * sens

    if emotion not in core:
        core[emotion] = 0.5

    # If it's already very strong, tiny nudges are skipped
    if abs(scaled_amount) < 0.1 and abs(core[emotion] - 0.5) > 0.4:
        log_private(f"Emotion '{emotion}' too strong to shift by {scaled_amount}. Skipped.")
        return

    new_value = round(core[emotion] + scaled_amount, 4)
    core[emotion] = max(0.0, min(1.0, new_value))

    stability = float(state.get("emotional_stability", 1.0))
    if scaled_amount > 0:
        stability = min(1.0, stability + (scaled_amount * 0.1))
    elif scaled_amount < 0:
        stability = max(0.0, stability - (abs(scaled_amount) * 0.1))

    state["core_emotions"] = core
    state["emotional_stability"] = round(stability, 4)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    state.setdefault("recent_triggers", []).append({
        "event": reason or f"adjusted_{emotion}",
        "emotion": emotion,
        "intensity": round(scaled_amount, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    save_json(state_path, state)
    log_private(f"Emotion adjusted: {emotion} by {round(scaled_amount, 4)} due to {reason or 'unspecified'}")

    # Add a thalamus signal if a context is provided
    if context is not None:
        context.setdefault("raw_signals", []).append({
            "source": "emotion",
            "content": f"Emotion adjusted: {emotion} by {round(scaled_amount, 4)} due to {reason or 'unspecified'}",
            "signal_strength": min(max(abs(scaled_amount), 0.3), 1.0),
            "tags": ["emotion", "internal", str(emotion), str(reason or "adjustment")],
        })


def detect_emotion(text: str) -> str:
    text = (text or "").lower()
    emotion_keywords = load_emotion_keywords()
    if not emotion_keywords:
        log_error(f"⚠️ No emotion keywords loaded — returning 'neutral' for: {text[:100]}")
        return "neutral"

    emotion_scores = {emotion: 0 for emotion in emotion_keywords}
    for emotion, keywords in emotion_keywords.items():
        for word in keywords:
            if word in text:
                emotion_scores[emotion] += 1

    return max(emotion_scores, key=emotion_scores.get) if any(emotion_scores.values()) else "neutral"


def log_pain(context, emotion: str = "frustration", increment: float = 0.3):
    from utils.json_utils import load_json, save_json
    from paths import EMOTIONAL_STATE_FILE as _STATE_FILE

    full_state = load_json(_STATE_FILE, default_type=dict)
    core_emotions = dict(full_state.get("core_emotions", {}))

    core_emotions[emotion] = min(core_emotions.get(emotion, 0.0) + float(increment), 1.0)
    full_state["core_emotions"] = core_emotions
    context["emotional_state"] = full_state

    save_json(_STATE_FILE, full_state)
    log_private(f"⚠️ Pain signal: {emotion} increased to {core_emotions[emotion]}")

    context.setdefault("raw_signals", []).append({
        "source": "emotion",
        "content": f"Pain signal: {emotion} increased to {core_emotions[emotion]}",
        "signal_strength": min(max(float(increment), 0.3), 1.0),
        "tags": ["emotion", "pain", "internal", str(emotion)],
    })


def log_uncertainty_spike(context, increment: float = 0.2):
    log_private("😵 Disorientation: No function selected by think()")
    log_pain(context, emotion="uncertainty", increment=increment)


def contextual_emotion_priming(context, persist: bool = True):
    """Affective priming based on working memory, triggers, goals, and mode."""
    emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)[-12:]
    self_model = get_self_model()
    mode = load_json(MODE_FILE, default_type=dict).get("mode", "neutral")

    core_emotions = dict(emotional_state.get("core_emotions", {}))
    recent_triggers = emotional_state.get("recent_triggers", [])[-10:]
    motivations = [m.lower() for m in self_model.get("motivations", []) if isinstance(m, str)]

    influence_map = {}

    # 1) Working memory echoes
    for memory in working_memory:
        # new-style emotion dict
        emotion_data = memory.get("emotion")
        if isinstance(emotion_data, dict):
            em = emotion_data.get("emotion")
            intensity = float(emotion_data.get("intensity", 0.5))
            if em:
                influence_map[em] = influence_map.get(em, 0.0) + intensity * 0.5

        # fallback old-style valence
        valence = memory.get("emotional_valence", {})
        if isinstance(valence, dict):
            for em, intensity in valence.items():
                influence_map[em] = influence_map.get(em, 0.0) + float(intensity) * 0.5

    # 2) Trigger echoes
    for trig in recent_triggers:
        em = trig.get("emotion")
        intensity = float(trig.get("intensity", 0.5))
        if em:
            influence_map[em] = influence_map.get(em, 0.0) + intensity * 0.4

    # 3) Goal-based semantic priming
    goal_bias_map = {
        "connection": "affection",
        "achievement": "pride",
        "progress": "motivation",
        "safety": "anxiety",
        "stability": "security",
    }
    for goal in motivations:
        for keyword, bias_emotion in goal_bias_map.items():
            if keyword in goal:
                influence_map[bias_emotion] = influence_map.get(bias_emotion, 0.0) + 0.3

    # 4) Mode-based modulation
    mode_bias = {
        "creative": "curiosity",
        "critical": "frustration",
        "adaptive": "neutral",
        "philosophical": "melancholy",
        "exploratory": "surprise",
    }
    mode_emotion = mode_bias.get(mode)
    if mode_emotion:
        influence_map[mode_emotion] = influence_map.get(mode_emotion, 0.0) + 0.2

    # 5) Apply updates
    total_delta = 0.0
    for em, delta in influence_map.items():
        prev = float(core_emotions.get(em, 0.5))
        updated = min(1.0, max(0.0, prev + delta * 0.2))
        total_delta += abs(updated - prev)
        core_emotions[em] = round(updated, 3)

    emotional_state["core_emotions"] = core_emotions

    # 6) Reward feedback loop
    reward_strength = min(1.0, total_delta / max(len(influence_map), 1))
    release_reward_signal(
        context=context,  # use the actual context for consistency
        signal_type="dopamine",
        actual_reward=reward_strength,
        expected_reward=0.5,
        effort=0.4,
        mode="tonic",
    )

    # 7) Save and inject
    if persist:
        save_json(EMOTIONAL_STATE_FILE, emotional_state)

    context["emotional_state"] = emotional_state
    log_activity("[Priming] Contextual emotion priming dynamically updated emotional profile.")


def dominant_emotion(emotional_state) -> str:
    """Return the dominant emotion from a full emotional_state dict."""
    if not isinstance(emotional_state, dict):
        return "neutral"
    core = emotional_state.get("core_emotions", {})
    if not isinstance(core, dict) or not core:
        return "neutral"
    return max(core, key=core.get)