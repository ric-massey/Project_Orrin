
from statistics import mean
import random

from utils.response_utils import generate_response_from_context
from utils.load_utils import load_all_known_json
from utils.log import log_private
from utils.log_reflection import log_reflection
from utils.coerce_to_string import coerce_to_string
from emotion.discovery import discover_new_emotion
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reflect_on_emotion_model import reflect_on_emotion_model
from emotion.emotion import investigate_unexplained_emotions, detect_emotion


def reflect_on_emotions(context, self_model, memory):
    from memory.working_memory import update_working_memory
    from datetime import datetime, timezone
    data = load_all_known_json()
    emotional_state = data.get("emotional_state", {})
    sensitivity = data.get("emotion_sensitivity", {})
    attachment = emotional_state.get("attachment", {})
    core = emotional_state.get("core_emotions", {})
    triggers = emotional_state.get("recent_triggers", [])[-10:]
    stability = emotional_state.get("emotional_stability", 0.5)
    fatigue = emotional_state.get("fatigue", 0.0)
    motivation = emotional_state.get("motivation", 0.5)
    excitement = emotional_state.get("excitement", 0.0)

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

    context_for_llm = {
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

    context_for_llm["instructions"] = coerce_to_string(context_for_llm["instructions"])
    response = generate_response_from_context(context_for_llm)

    now = datetime.now(timezone.utc).isoformat()

    if response:
        update_working_memory({
            "content": "emotional reflection: " + response,
            "event_type": "emotional_reflection",
            "emotion": detect_emotion(response),
            "timestamp": now,
            "importance": 2,
            "priority": 2,
            "referenced": 1,
            "recall_count": 0,
            "related_memory_id": None,
            "decay": 1.0,
            "tags": ["reflection", "emotion"]
        })
        log_private(f"[emotional reflection - {now}]\n{response}")
        log_reflection(f"Self-belief reflection: {response.strip()}")

        # --- Calculate reward parameters dynamically ---
        base_actual_reward = 0.6 + min(0.4, 1.0 - stability)
        # Modulate actual reward downward if fatigued, upwards if motivated/excited
        modulated_actual_reward = base_actual_reward * (1 - fatigue * 0.4) * (1 + 0.3 * (motivation + excitement))
        # Clamp to [0,1]
        modulated_actual_reward = max(0.0, min(modulated_actual_reward, 1.0))

        base_effort = 0.5 + (0.5 if all(val < 0.2 for val in emotion_variability) else 0.0)
        modulated_effort = base_effort * (1 - fatigue * 0.5) * (1 + 0.2 * motivation)
        modulated_effort = max(0.1, min(modulated_effort, 1.0))

        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=modulated_actual_reward,
            expected_reward=0.7,
            effort=modulated_effort,
            mode="phasic"
        )
    else:
        update_working_memory({
            "content": "⚠️ Emotional reflection failed or returned nothing.",
            "event_type": "emotional_reflection",
            "emotion": "neutral",
            "timestamp": now,
            "importance": 2,
            "priority": 1,
            "referenced": 0,
            "recall_count": 0,
            "related_memory_id": None,
            "decay": 1.0,
            "tags": ["reflection", "emotion", "error"]
        })
        # Give a minimal dopamine reward on failure
        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=0.1,
            expected_reward=0.7,
            effort=0.6,
            mode="phasic"
        )
        