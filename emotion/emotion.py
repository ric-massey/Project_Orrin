# == Imports
from datetime import datetime, timezone
from statistics import mean
import random
import re

# === Internal Utility Imports ===
from utils.generate_response import generate_response, get_thinking_model
from utils.response_utils import generate_response_from_context
from utils.load_utils import load_all_known_json
from utils.json_utils import load_json, save_json, extract_json
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from utils.coerce_to_string import coerce_to_string
from emotion.discovery import discover_new_emotion
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reflect_on_emotion_model import reflect_on_emotion_model
from emotion.modes_and_emotion import (
    recommend_mode_from_emotional_state, set_current_mode, get_current_mode
)
from utils.timing import get_time_since_last_active


# === File Constants ===
from paths import (
    EMOTIONAL_STATE_FILE, LONG_MEMORY_FILE, 
    MODEL_CONFIG_FILE, WORKING_MEMORY_FILE, 
    EMOTION_MODEL_FILE, CUSTOM_EMOTION

)

def reflect_on_emotions(context, self_model, memory):
    from memory.working_memory import update_working_memory
    data = load_all_known_json()
    emotional_state = data.get("emotional_state", {})
    sensitivity = data.get("emotion_sensitivity", {})
    attachment = emotional_state.get("attachment", {})
    core = emotional_state.get("core_emotions", {})
    triggers = emotional_state.get("recent_triggers", [])[-10:]
    stability = emotional_state.get("emotional_stability", 0.5)

    # === Emotion Summary ===
    emotion_events = {}
    for trig in triggers:
        emo = trig.get("emotion")
        intensity = abs(trig.get("intensity", 0))
        if emo:
            emotion_events.setdefault(emo, []).append(intensity)

    emotion_summary = [
        f"- {emo} triggered {len(vals)}x (avg intensity: {round(mean(vals), 3)})"
        for emo, vals in emotion_events.items()
    ]

    strongest = sorted(core.items(), key=lambda x: abs(x[1] - 0.5), reverse=True)[:5]
    emotion_variability = [abs(v - 0.5) for _, v in strongest]

    # === Trigger emotion model expansion if emotion range is flat ===
    if all(val < 0.2 for val in emotion_variability):  # flat affect
        discover_new_emotion()
        reflect_on_emotion_model(context, self_model, memory)

    # === Occasional reflection on emotion model (1%) ===
    if random.random() < 0.01:
        reflect_on_emotion_model(context, self_model, memory)

    # === Trigger introspection if strong emotion lacks known cause (70%) ===
    threshold = 0.4
    unexplained = {
        emo: val for emo, val in core.items()
        if val >= threshold and not any(t.get("emotion") == emo for t in triggers)
    }
    if unexplained and random.random() < 0.7:
        investigate_unexplained_emotions(context, self_model, memory)

    # === Build reflection context ===
    top_emotions = ", ".join(f"{k} ({round(v, 2)})" for k, v in strongest)
    top_sens = sorted(sensitivity.items(), key=lambda x: x[1], reverse=True)[:3]
    top_sensitivity = ", ".join(f"{k} ({round(v, 2)})" for k, v in top_sens)
    top_attach = sorted(attachment.items(), key=lambda x: x[1], reverse=True)[:3]
    top_attachments = ", ".join(f"{k} ({round(v, 2)})" for k, v in top_attach)

    context = {
        **data,
        "emotions": core,
        "recent_triggers": triggers,
        "emotion_summary": emotion_summary,
        "strongest_emotions": strongest,
        "emotional_stability": stability,
        "top_sensitivity": top_sensitivity,
        "top_attachments": top_attachments,
        "instructions": (
            f"I am currently experiencing these strong emotions: {top_emotions}\n"
            f"My most sensitive areas are: {top_sensitivity}\n"
            f"My strongest attachments are: {top_attachments}\n"
            f"My recent emotional triggers:\n" + "\n".join(emotion_summary) + "\n\n"
            "Reflect honestly on my emotional state. Use all available knowledge:\n"
            "- What patterns are forming?\n"
            "- Am I feeling more reactive or stable?\n"
            "- Am I stuck in an emotion loop?\n"
            "- Do my emotions match my values and self-beliefs?\n"
            "- Is there decay or dysregulation pulling me away from balance?\n"
            "Be honest, not performative. Tell the emotional truth."
        )
    }

    context["instructions"] = coerce_to_string(context["instructions"])
    response = generate_response_from_context(context)

    if response:
        update_working_memory("emotional reflection: " + response)
        log_private(f"[emotional reflection - {datetime.now(timezone.utc)}]\n{response}")
        log_reflection(f"Self-belief reflection: {response.strip()}")

        actual_reward = 0.6 + min(0.4, 1.0 - stability)
        expected_reward = 0.7
        effort = 0.5 + (0.5 if all(val < 0.2 for val in emotion_variability) else 0.0)

        release_reward_signal(
            context=emotional_state,
            signal_type="dopamine",
            actual_reward=actual_reward,
            expected_reward=expected_reward,
            effort=effort,
            mode="phasic"
        )
    else:
        update_working_memory("⚠️ Emotional reflection failed or returned nothing.")
        release_reward_signal(
            context=emotional_state,
            signal_type="dopamine",
            actual_reward=0.1,
            expected_reward=0.7,
            effort=0.6,
            mode="phasic"
        )


def investigate_unexplained_emotions(context, self_model, memory):
    from memory.working_memory import update_working_memory
    from emotion.reward_signals.reward_signals import release_reward_signal

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

    if not unexplained:
        update_working_memory("All current strong emotions are accounted for.")
        release_reward_signal(
            context=context.get("emotional_state", {}),
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
        update_working_memory("Unexplained emotion reflection:\n" + reflection)

        for emo in unexplained:
            emotional_state.setdefault("recent_triggers", []).append({
                "event": "unexplained emotion reflection",
                "emotion": emo,
                "intensity": core_emotions[emo],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        save_json(EMOTIONAL_STATE_FILE, emotional_state)

        release_reward_signal(
            context=context.get("emotional_state", {}),
            signal_type="dopamine",
            actual_reward=0.75,
            expected_reward=0.5,
            effort=0.6,
            mode="phasic"
        )
    else:
        update_working_memory("⚠️ Failed to generate a reflection on unexplained emotions.")
        release_reward_signal(
            context=context.get("emotional_state", {}),
            signal_type="dopamine",
            actual_reward=0.1,
            expected_reward=0.4,
            effort=0.5,
            mode="phasic"
        )


from paths import EMOTION_MODEL_FILE, CUSTOM_EMOTION

def detect_emotion(text, use_gpt=True):
    text = text.lower()
    emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
    custom_emotions = load_json(CUSTOM_EMOTION, default_type=list)

    # === Build dynamic keyword map ===
    emotion_keywords = {k: v for k, v in emotion_model.items()}
    for emo in custom_emotions:
        name = emo.get("name")
        desc = emo.get("description", "")
        if name:
            words = re.findall(r'\b\w+\b', desc.lower())
            emotion_keywords.setdefault(name, []).extend(words)

    # === Simple keyword-based detection ===
    scores = {emotion: 0 for emotion in emotion_keywords}
    for emotion, keywords in emotion_keywords.items():
        for word in keywords:
            if word in text:
                scores[emotion] += 1

    top_emotion = max(scores, key=scores.get)
    intensity = min(scores[top_emotion] / 5.0, 1.0)

    if scores[top_emotion] > 0:
        return {
            "emotion": top_emotion,
            "intensity": round(intensity, 2)
        }

    # === GPT fallback if keyword match fails ===
    if use_gpt:
        prompt = (
            "Analyze the following message and infer the emotion and its strength.\n"
            f"Message: \"{text}\"\n\n"
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

    # === Final fallback ===
    return {
        "emotion": "neutral",
        "intensity": 0.0
    }

def deliver_emotion_based_rewards(context, core_emotions, stability):
    from emotion.reward_signals.reward_signals import release_reward_signal

    dominant = max(core_emotions, key=core_emotions.get)
    intensity = core_emotions[dominant]

    if dominant == "joy":
        release_reward_signal(context, "dopamine", actual_reward=intensity, expected_reward=0.5)
    elif dominant in ["fear", "sadness"]:
        release_reward_signal(context, "dopamine", actual_reward=0.1, expected_reward=0.5)
    elif stability < 0.4:
        release_reward_signal(context, "pain", actual_reward=1.0, expected_reward=0.0)

    if intensity > 0.8:
        release_reward_signal(context, "novelty", actual_reward=intensity, expected_reward=0.3)

def get_all_emotion_names():
    """Load emotion names from emotion model JSON."""
    data = load_json(EMOTION_MODEL_FILE, default_type=dict)
    return list(data.keys()) if isinstance(data, dict) else []

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
        # High in curiosity and reflection, low in jealousy and anger
        "curious": 0.25,
        "reflective": 0.35,
        "analytical": 0.2,
        "compassionate": 0.1,
        "joyful": 0.1,
        "hopeful": 0.08,
        "melancholy": 0.04,
        "jealous": 0.01,
        "angry": 0.01,
        # All others default to 0
    }

    # --- Opposites for cross-inhibition (always accessible) ---
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
    for emo in list(core.keys()):
        if emo not in model_emotions:
            del core[emo]

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
        # Optionally, reduce joy/hopeful
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
        # If an emotion spikes, lower opposite/conflicting emotions
        nudges = trigger_map.get(trigger, {})
        for emo, boost in nudges.items():
            if emo in core:
                core[emo] = min(1.0, core[emo] + boost)
                # Suppress opposites a bit
                for opp in opposites.get(emo, []):
                    if opp in core:
                        core[opp] = max(baseline.get(opp, 0.0), core[opp] - boost * 0.7)

    # === Decay Emotions Over Time ===
    for emo in core:
        if state.get("emotional_decay", True):
            # Decay toward each emotion's personal baseline (usually 0, but some can be higher)
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
            # Cross-inhibit opposites here as well
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