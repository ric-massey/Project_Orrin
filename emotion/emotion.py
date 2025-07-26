from statistics import mean
import re
# === Internal Utility Imports ===
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import load_json, save_json, extract_json
from utils.log import log_error
from utils.coerce_to_string import coerce_to_string
# === File Constants ===
from paths import (
    EMOTIONAL_STATE_FILE, LONG_MEMORY_FILE, 
    MODEL_CONFIG_FILE,
    EMOTION_MODEL_FILE, CUSTOM_EMOTION
)


def investigate_unexplained_emotions(context, self_model, memory):
    from memory.working_memory import update_working_memory
    from emotion.reward_signals.reward_signals import release_reward_signal
    from datetime import datetime, timezone

    emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    config = load_json(MODEL_CONFIG_FILE, default_type=dict)

    threshold = config.get("emotion_analysis_threshold", 0.4)
    core_emotions = emotional_state.get("core_emotions", {})
    recent_triggers = emotional_state.get("recent_triggers", [])[-10:]

    unexplained = {
        emotion: value
        for emotion, value in core_emotions.items()
        if value >= threshold and not any(trigger.get("emotion") == emotion for trigger in recent_triggers)
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
            "tags": ["emotion", "reflection"]
        })
        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=0.2,
            expected_reward=0.3,
            effort=0.2,
            mode="tonic"
        )
        return

    past_reflections = [entry["content"] for entry in long_memory[-20:] if "content" in entry]
    context_block = "\n".join(f"- {item}" for item in past_reflections)
    emotional_summary = "\n".join(f"{k}: {v}" for k, v in unexplained.items())

    prompt = (
        "I am Orrin, reflecting on unexplained emotional intensities.\n"
        f"Unexplained emotions:\n{emotional_summary}\n\n"
        "Here are recent memories and reflections:\n"
        f"{context_block}\n\n"
        "Try to hypothesize what could be causing these emotional patterns. If I cannot explain them, say so."
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
            "tags": ["emotion", "reflection", "unexplained"]
        })

        for emo in unexplained:
            emotional_state.setdefault("recent_triggers", []).append({
                "event": "unexplained emotion reflection",
                "emotion": emo,
                "intensity": core_emotions[emo],
                "timestamp": now
            })

        save_json(EMOTIONAL_STATE_FILE, emotional_state)

        # Modulate reward by fatigue and motivation if you want consistency
        fatigue = emotional_state.get("fatigue", 0.0)
        motivation = emotional_state.get("motivation", 0.5)

        base_actual_reward = 0.75
        modulated_actual_reward = base_actual_reward * (1 - fatigue * 0.4) * (1 + 0.3 * motivation)
        modulated_actual_reward = max(0.0, min(modulated_actual_reward, 1.0))

        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=modulated_actual_reward,
            expected_reward=0.5,
            effort=0.6,
            mode="phasic"
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
            "tags": ["emotion", "reflection", "unexplained", "error"]
        })
        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=0.1,
            expected_reward=0.4,
            effort=0.5,
            mode="phasic"
        )

def detect_emotion(text, use_gpt=True):
    import re

    text = text.lower()
    emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
    custom_emotions = load_json(CUSTOM_EMOTION, default_type=list)

    # Build dynamic keyword map
    emotion_keywords = {k: v[:] for k, v in emotion_model.items()}  # copy lists
    for emo in custom_emotions:
        name = emo.get("name")
        desc = emo.get("description", "")
        if name:
            words = re.findall(r'\b\w+\b', desc.lower())
            emotion_keywords.setdefault(name, []).extend(words)

    # Keyword-based detection with normalization
    scores = {}
    for emotion, keywords in emotion_keywords.items():
        count = 0
        for word in keywords:
            if word in text:
                count += 1
        # Normalize by total keywords to avoid bias
        scores[emotion] = count / max(len(keywords), 1)

    top_emotion = max(scores, key=scores.get)
    intensity = min(scores[top_emotion], 1.0)

    if scores[top_emotion] > 0:
        return {
            "emotion": top_emotion,
            "intensity": round(intensity, 2)
        }

    # GPT fallback
    if use_gpt:
        safe_text = (text or "").strip()
        if not safe_text or safe_text in {"—", "-", "--", "---"}:
            return {"emotion": "neutral", "intensity": 0.0}
        prompt = (
            "Analyze the following message and infer the emotion and its strength.\n"
            f"Message: \"{safe_text}\"\n\n"
            "Respond ONLY with a JSON object:\n"
            "{ \"emotion\": \"emotion_name\", \"intensity\": 0.0 to 1.0 }"
        )
        try:
            result = generate_response(prompt, config={"model": get_thinking_model()})
            data = extract_json(result.strip()) if "{" in result else {}
            if isinstance(data, dict) and "emotion" in data:
                return {
                    "emotion": str(data.get("emotion", "neutral")).lower(),
                    "intensity": round(float(data.get("intensity", 0.5)), 2)
                }
        except Exception as e:
            log_error(f"❌ detect_emotion GPT fallback failed: {e}")

    return {
        "emotion": "neutral",
        "intensity": 0.0
    }

def deliver_emotion_based_rewards(context, core_emotions, stability):
    from emotion.reward_signals.reward_signals import release_reward_signal

    if not core_emotions:
        return

    dominant = max(core_emotions, key=core_emotions.get)
    intensity = core_emotions[dominant]

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
            mode=phasic_mode
        )
    elif dominant in ["fear", "sadness"]:
        release_reward_signal(
            context,
            "dopamine",
            actual_reward=0.1,
            expected_reward=0.5,
            effort=base_effort,
            mode=tonic_mode
        )
    elif stability < 0.4:
        release_reward_signal(
            context,
            "serotonin",  # Use serotonin or a supported signal instead of 'pain'
            actual_reward=1.0,
            expected_reward=0.0,
            effort=base_effort,
            mode=phasic_mode
        )

    if intensity > 0.8:
        release_reward_signal(
            context,
            "novelty",
            actual_reward=intensity,
            expected_reward=0.3,
            effort=base_effort,
            mode=phasic_mode
        )


def get_all_emotion_names():
    """Load emotion names from emotion model JSON."""
    data = load_json(EMOTION_MODEL_FILE, default_type=dict)
    return list(data.keys()) if isinstance(data, dict) else []