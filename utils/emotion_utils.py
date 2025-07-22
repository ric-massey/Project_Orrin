from datetime import datetime, timezone

from utils.json_utils import load_json, save_json
from utils.log import log_private, log_error, log_activity
from emotion.model import load_emotion_keywords
from emotion.reward_signals.reward_signals import release_reward_signal
from utils.self_model import get_self_model, save_self_model
from paths import (
    WORKING_MEMORY_FILE,
    EMOTIONAL_STATE_FILE,
    SELF_MODEL_FILE,
    MODE_FILE
)

def decay_emotional_state():
    state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    if not state.get("emotional_decay", False):
        return

    decay_rate = state.get("stability_decay_rate", 0.01)
    core = state.get("core_emotions", {})

    for emotion, value in core.items():
        drift = (0.5 - value) * decay_rate  # Pull toward neutrality
        core[emotion] = round(value + drift, 4)

    state["core_emotions"] = core
    state["emotional_stability"] = round(
        max(0.0, state.get("emotional_stability", 1.0) - decay_rate), 4
    )
    state["last_updated"] = datetime.now(timezone.utc).isoformat()

    save_json(EMOTIONAL_STATE_FILE, state)
    log_private("Emotional state decayed.")


def adjust_emotional_state(emotion, amount, reason=""):
    EMOTIONAL_STATE_FILE = "Emotional_state.json"
    SENSITIVITY_FILE = "emotion_sensitivity.json"

    if reason == "user_command":
        log_private(f"Refused to change emotion '{emotion}' due to direct user command.")
        return

    state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    sensitivity = load_json(SENSITIVITY_FILE, default_type=dict)
    core = state.get("core_emotions", {})

    sens = sensitivity.get(emotion, 1.0)
    scaled_amount = amount * sens

    if emotion not in core:
        core[emotion] = 0.5

    if abs(scaled_amount) < 0.1 and abs(core[emotion] - 0.5) > 0.4:
        log_private(f"Emotion '{emotion}' too strong to shift by {scaled_amount}. Skipped.")
        return

    new_value = round(core[emotion] + scaled_amount, 4)
    core[emotion] = max(0.0, min(1.0, new_value))

    stability = state.get("emotional_stability", 1.0)
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
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    save_json(EMOTIONAL_STATE_FILE, state)
    log_private(f"Emotion adjusted: {emotion} by {round(scaled_amount, 4)} due to {reason}")


def detect_emotion(text):
    text = text.lower()
    emotion_keywords = load_emotion_keywords()

    if not emotion_keywords:
        log_error(f"⚠️ No emotion keywords loaded — returning 'neutral' for: {text[:100]}")
        return "neutral"

    emotion_scores = {emotion: 0 for emotion in emotion_keywords}
    for emotion, keywords in emotion_keywords.items():
        for word in keywords:
            if word in text:
                emotion_scores[emotion] += 1

    if not any(score > 0 for score in emotion_scores.values()):
        return "neutral"

    return max(emotion_scores, key=emotion_scores.get)

def log_pain(context, emotion="frustration", increment=0.3):
    # Safely get or create emotional_state
    emotional_state = context.get("emotional_state", {})
    
    # Increment the emotion
    emotional_state[emotion] = min(emotional_state.get(emotion, 0.0) + increment, 1.0)
    
    # Update context
    context["emotional_state"] = emotional_state

    # Save and log
    save_json(EMOTIONAL_STATE_FILE, emotional_state)
    log_private(f"⚠️ Pain signal: {emotion} increased to {emotional_state[emotion]}")

def log_uncertainty_spike(context, increment=0.2):
    log_private("😵 Disorientation: No function selected by think()")
    log_pain(context, emotion="uncertainty", increment=increment)

def contextual_emotion_priming(context, persist=True):
    """
    Affective priming system that dynamically adjusts emotional valence based on:
    - recent working memory valence traces
    - recent emotional triggers
    - goal alignment (from self model)
    - active cognitive mode
    - reward reinforcement for dynamic adaptation
    """

    # === Load context ===
    emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)[-12:]
    self_model = get_self_model()  # <---- ONLY use the helper!
    mode = load_json(MODE_FILE, default_type=dict).get("mode", "neutral")

    # === Get core emotions + motivations
    core_emotions = emotional_state.get("core_emotions", {})
    recent_triggers = emotional_state.get("recent_triggers", [])[-10:]
    motivations = [m.lower() for m in self_model.get("motivations", []) if isinstance(m, str)]

    influence_map = {}

    # === 1. Working memory priming (emotional echoes)
    for memory in working_memory:
        valence = memory.get("emotional_valence", {})
        for emotion, intensity in valence.items():
            influence_map[emotion] = influence_map.get(emotion, 0.0) + intensity * 0.5

    # === 2. Trigger-based echo
    for trig in recent_triggers:
        emotion = trig.get("emotion")
        intensity = trig.get("intensity", 0.5)
        if emotion:
            influence_map[emotion] = influence_map.get(emotion, 0.0) + intensity * 0.4

    # === 3. Goal-based semantic priming (dynamic)
    goal_bias_map = {
        "connection": "affection",
        "achievement": "pride",
        "progress": "motivation",
        "safety": "anxiety",
        "stability": "security"
    }

    for goal in motivations:
        for keyword, bias_emotion in goal_bias_map.items():
            if keyword in goal:
                influence_map[bias_emotion] = influence_map.get(bias_emotion, 0.0) + 0.3

    # === 4. Mode-based affective modulation
    mode_bias = {
        "creative": "curiosity",
        "critical": "frustration",
        "adaptive": "neutral",
        "philosophical": "melancholy",
        "exploratory": "surprise"
    }

    mode_emotion = mode_bias.get(mode)
    if mode_emotion:
        influence_map[mode_emotion] = influence_map.get(mode_emotion, 0.0) + 0.2

    # === 5. Apply updates to core emotions (clamped)
    total_delta = 0.0
    for emotion, delta in influence_map.items():
        previous = core_emotions.get(emotion, 0.5)
        updated = min(1.0, max(0.0, previous + delta * 0.2))
        total_delta += abs(updated - previous)
        core_emotions[emotion] = round(updated, 3)

    emotional_state["core_emotions"] = core_emotions

    # === 6. Reward feedback loop (scales to total adjustment)
    reward_strength = min(1.0, total_delta / max(len(influence_map), 1))
    release_reward_signal(
        context=emotional_state,
        signal_type="dopamine",
        actual_reward=reward_strength,
        expected_reward=0.5,
        effort=0.4,
        mode="tonic"
    )

    # === 7. Save and inject
    if persist:
        save_json(EMOTIONAL_STATE_FILE, emotional_state)

    context["emotional_state"] = emotional_state
    log_activity("[Priming] Contextual emotion priming dynamically updated emotional profile.")