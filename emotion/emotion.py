# === Internal Utility Imports ===
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import load_json, save_json, extract_json
from utils.log import log_error
from utils.coerce_to_string import coerce_to_string

# === File Constants ===
from paths import (
    EMOTIONAL_STATE_FILE,
    LONG_MEMORY_FILE,
    MODEL_CONFIG_FILE,
    EMOTION_MODEL_FILE,
    CUSTOM_EMOTION,
)


def investigate_unexplained_emotions(context, self_model, memory):
    from memory.working_memory import update_working_memory
    from emotion.reward_signals.reward_signals import release_reward_signal
    from datetime import datetime, timezone

    emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    if not isinstance(emotional_state, dict):
        emotional_state = {}

    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        long_memory = []

    config = load_json(MODEL_CONFIG_FILE, default_type=dict)
    if not isinstance(config, dict):
        config = {}

    threshold = float(config.get("emotion_analysis_threshold", 0.4))

    core_emotions = emotional_state.get("core_emotions", {})
    if not isinstance(core_emotions, dict):
        core_emotions = {}

    recent_triggers = emotional_state.get("recent_triggers", [])
    if not isinstance(recent_triggers, list):
        recent_triggers = []
    recent_triggers = recent_triggers[-10:]

    unexplained = {
        emotion: value
        for emotion, value in core_emotions.items()
        if isinstance(value, (int, float))
        and value >= threshold
        and not any(
            isinstance(trigger, dict) and trigger.get("emotion") == emotion
            for trigger in recent_triggers
        )
    }

    now = datetime.now(timezone.utc).isoformat()

    if not unexplained:
        update_working_memory({
            "content": "All current strong emotions are accounted for.",
            "event_type": "emotion_analysis",
            "emotion": "neutral",
            "timestamp": now,
            "importance": 1,
            "priority": 1,
            "referenced": 0,
            "recall_count": 0,
            "related_memory_id": None,
            "decay": 1.0,
            "tags": ["emotion", "reflection"],
        })
        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=0.2,
            expected_reward=0.3,
            effort=0.2,
            mode="tonic",
        )
        return

    past_reflections = [
        entry.get("content", "")
        for entry in long_memory[-20:]
        if isinstance(entry, dict) and entry.get("content")
    ]
    context_block = "\n".join(f"- {item}" for item in past_reflections)
    emotional_summary = "\n".join(f"{k}: {v}" for k, v in unexplained.items())

    prompt = (
        "I am Orrin, reflecting on unexplained emotional intensities.\n"
        f"Unexplained emotions:\n{emotional_summary}\n\n"
        "Here are recent memories and reflections:\n"
        f"{context_block}\n\n"
        "Try to hypothesize what could be causing these emotional patterns. "
        "If I cannot explain them, say so."
    )

    reflection = generate_response(coerce_to_string(prompt))

    if reflection:
        update_working_memory({
            "content": "Unexplained emotion reflection:\n" + reflection,
            "event_type": "unexplained_emotion_reflection",
            "emotion": "uncertain",
            "timestamp": now,
            "importance": 2,
            "priority": 2,
            "referenced": 1,
            "recall_count": 0,
            "related_memory_id": None,
            "decay": 1.0,
            "tags": ["emotion", "reflection", "unexplained"],
        })

        for emo in unexplained:
            emotional_state.setdefault("recent_triggers", []).append({
                "event": "unexplained emotion reflection",
                "emotion": emo,
                "intensity": core_emotions.get(emo, 0.0),
                "timestamp": now,
            })

        save_json(EMOTIONAL_STATE_FILE, emotional_state)

        # Modulate reward by fatigue and motivation for consistency
        fatigue = float(emotional_state.get("fatigue", 0.0))
        motivation = float(emotional_state.get("motivation", 0.5))

        base_actual_reward = 0.75
        modulated_actual_reward = base_actual_reward * (1 - fatigue * 0.4) * (1 + 0.3 * motivation)
        modulated_actual_reward = max(0.0, min(modulated_actual_reward, 1.0))

        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=modulated_actual_reward,
            expected_reward=0.5,
            effort=0.6,
            mode="phasic",
        )
    else:
        update_working_memory({
            "content": "⚠️ Failed to generate a reflection on unexplained emotions.",
            "event_type": "unexplained_emotion_reflection",
            "emotion": "neutral",
            "timestamp": now,
            "importance": 1,
            "priority": 1,
            "referenced": 0,
            "recall_count": 0,
            "related_memory_id": None,
            "decay": 1.0,
            "tags": ["emotion", "reflection", "unexplained", "error"],
        })
        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=0.1,
            expected_reward=0.4,
            effort=0.5,
            mode="phasic",
        )


def detect_emotion(text, use_gpt=True):
    import re

    # Normalize input
    text = (text or "").strip()
    if not isinstance(text, str) or not text:
        return {"emotion": "neutral", "intensity": 0.0}
    text_lc = text.lower()

    # Load models defensively
    emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
    if not isinstance(emotion_model, dict):
        emotion_model = {}

    custom_emotions = load_json(CUSTOM_EMOTION, default_type=list)
    if not isinstance(custom_emotions, list):
        custom_emotions = []

    # Build dynamic keyword map (dedupe, keep words >= 3 chars)
    emotion_keywords = {}
    for k, v in emotion_model.items():
        if not isinstance(k, str):
            continue
        kws = [str(w).lower().strip() for w in (v or []) if isinstance(w, (str, int, float))]
        kws = [w for w in kws if len(w) >= 3]
        if kws:
            emotion_keywords[k] = list(dict.fromkeys(kws))  # dedupe

    for emo in custom_emotions:
        if not isinstance(emo, dict):
            continue
        name = emo.get("name")
        desc = emo.get("description", "")
        if isinstance(name, str) and name.strip():
            words = re.findall(r'\b\w+\b', str(desc).lower())
            words = [w for w in words if len(w) >= 3]
            if words:
                emotion_keywords.setdefault(name, []).extend(words)

    # Keyword-based detection
    scores = {}
    for emotion, keywords in emotion_keywords.items():
        if not keywords:
            continue
        count = 0
        for word in keywords:
            if word in text_lc:
                count += 1
        scores[emotion] = count / max(len(keywords), 1)

    if scores:
        top_emotion = max(scores, key=scores.get)
        intensity = min(scores.get(top_emotion, 0.0), 1.0)
        if intensity > 0.0:
            return {
                "emotion": str(top_emotion).lower(),
                "intensity": round(float(intensity), 2),
            }

    # GPT fallback
    if use_gpt:
        prompt = (
            "Analyze the following message and infer the emotion and its strength.\n"
            f"Message: \"{text}\"\n\n"
            "Respond ONLY with a JSON object:\n"
            "{ \"emotion\": \"emotion_name\", \"intensity\": 0.0 to 1.0 }"
        )
        try:
            result = generate_response(prompt, config={"model": get_thinking_model()})
            data = extract_json(result.strip()) if result and "{" in result else {}
            if isinstance(data, dict) and "emotion" in data:
                return {
                    "emotion": str(data.get("emotion", "neutral")).lower(),
                    "intensity": round(float(data.get("intensity", 0.5)), 2),
                }
        except Exception as e:
            log_error(f"❌ detect_emotion GPT fallback failed: {e}")

    return {"emotion": "neutral", "intensity": 0.0}


def deliver_emotion_based_rewards(context, core_emotions, stability):
    from emotion.reward_signals.reward_signals import release_reward_signal

    if not core_emotions or not isinstance(core_emotions, dict):
        return

    # Defensive: if dict empty, bail
    if not core_emotions:
        return

    dominant = max(core_emotions, key=core_emotions.get)
    intensity = float(core_emotions.get(dominant, 0.0))

    # Base effort and mode for rewards
    base_effort = 0.5
    phasic_mode = "phasic"
    tonic_mode = "tonic"

    if dominant == "joy":
        release_reward_signal(
            context,
            "dopamine",
            actual_reward=intensity,
            expected_reward=0.5,
            effort=base_effort,
            mode=phasic_mode,
        )
    elif dominant in ["fear", "sadness"]:
        release_reward_signal(
            context,
            "dopamine",
            actual_reward=0.1,
            expected_reward=0.5,
            effort=base_effort,
            mode=tonic_mode,
        )
    elif float(stability) < 0.4:
        release_reward_signal(
            context,
            "serotonin",  # supported signal
            actual_reward=1.0,
            expected_reward=0.0,
            effort=base_effort,
            mode=phasic_mode,
        )

    if intensity > 0.8:
        release_reward_signal(
            context,
            "novelty",
            actual_reward=intensity,
            expected_reward=0.3,
            effort=base_effort,
            mode=phasic_mode,
        )


def get_all_emotion_names():
    """Load emotion names from emotion model JSON."""
    data = load_json(EMOTION_MODEL_FILE, default_type=dict)
    return list(data.keys()) if isinstance(data, dict) else []