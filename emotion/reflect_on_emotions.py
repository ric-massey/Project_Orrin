# reflect_on_emotions.py
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
    emotional_state = data.get("emotional_state", {}) or {}
    sensitivity = data.get("emotion_sensitivity", {}) or {}
    attachment = emotional_state.get("attachment", {}) or {}
    core = emotional_state.get("core_emotions", {}) or {}
    triggers = emotional_state.get("recent_triggers", [])[-10:] or []

    # type guards
    if not isinstance(core, dict): core = {}
    if not isinstance(sensitivity, dict): sensitivity = {}
    if not isinstance(attachment, dict): attachment = {}
    if not isinstance(triggers, list): triggers = []

    stability = float(emotional_state.get("emotional_stability", 0.5) or 0.5)
    fatigue = float(emotional_state.get("fatigue", 0.0) or 0.0)
    motivation = float(emotional_state.get("motivation", 0.5) or 0.5)
    excitement = float(emotional_state.get("excitement", 0.0) or 0.0)

    # === Emotion Summary ===
    emotion_events = {}
    for trig in triggers:
        if not isinstance(trig, dict):  # guard malformed entries
            continue
        emo = trig.get("emotion")
        intensity = trig.get("intensity", 0)
        if emo and isinstance(intensity, (int, float)):
            emotion_events.setdefault(emo, []).append(abs(float(intensity)))

    emotion_summary = [
        f"- {emo} triggered {len(vals)}x (avg intensity: {round(mean(vals), 3)})"
        for emo, vals in emotion_events.items() if vals
    ]

    # strongest emotions by distance from neutral 0.5
    try:
        strongest = sorted(core.items(), key=lambda x: abs(float(x[1]) - 0.5), reverse=True)[:5]
    except Exception:
        strongest = []
    emotion_variability = [abs(float(v) - 0.5) for _, v in strongest] if strongest else []

    # === Trigger emotion model expansion if emotion range is flat ===
    if strongest and all(val < 0.2 for val in emotion_variability):  # flat affect
        discover_new_emotion(context=context)  # pass context for rewards
        reflect_on_emotion_model(context, self_model, memory)

    # === Occasional reflection on emotion model (1%) ===
    if random.random() < 0.01:
        reflect_on_emotion_model(context, self_model, memory)

    # === Trigger introspection if strong emotion lacks known cause (70%) ===
    threshold = 0.4
    unexplained = {
        emo: val for emo, val in core.items()
        if isinstance(val, (int, float))
        and val >= threshold
        and not any(isinstance(t, dict) and t.get("emotion") == emo for t in triggers)
    }
    if unexplained and random.random() < 0.7:
        investigate_unexplained_emotions(context, self_model, memory)

    # === Build reflection context ===
    top_emotions = ", ".join(f"{k} ({round(float(v), 2)})" for k, v in strongest) if strongest else "none"
    top_sens = sorted(sensitivity.items(), key=lambda x: x[1], reverse=True)[:3] if sensitivity else []
    top_sensitivity = ", ".join(f"{k} ({round(float(v), 2)})" for k, v in top_sens) if top_sens else "none"
    top_attach = sorted(attachment.items(), key=lambda x: x[1], reverse=True)[:3] if attachment else []
    top_attachments = ", ".join(f"{k} ({round(float(v), 2)})" for k, v in top_attach) if top_attach else "none"

    context_for_llm = {
        **data,
        "emotions": core,
        "recent_triggers": triggers,
        "emotion_summary": emotion_summary,
        "strongest_emotions": strongest,
        "emotional_stability": stability,
        "top_sensitivity": top_sensitivity,
        "top_attachments": top_attachments,
        "instructions": coerce_to_string(
            "I am currently experiencing these strong emotions: "
            f"{top_emotions}\n"
            f"My most sensitive areas are: {top_sensitivity}\n"
            f"My strongest attachments are: {top_attachments}\n"
            "My recent emotional triggers:\n" + "\n".join(emotion_summary) + "\n\n"
            "Reflect honestly on my emotional state. Use all available knowledge:\n"
            "- What patterns are forming?\n"
            "- Am I feeling more reactive or stable?\n"
            "- Am I stuck in an emotion loop?\n"
            "- Do my emotions match my values and self-beliefs?\n"
            "- Is there decay or dysregulation pulling me away from balance?\n"
            "Be honest, not performative. Tell the emotional truth."
        )
    }

    response = generate_response_from_context(context_for_llm)
    now = datetime.now(timezone.utc).isoformat()

    if isinstance(response, str) and response.strip():
        text = response.strip()
        det = detect_emotion(text) or {"emotion": "neutral", "intensity": 0.0}
        wm_emotion_name = det["emotion"] if isinstance(det, dict) else str(det)

        update_working_memory({
            "content": "emotional reflection: " + text,
            "event_type": "emotional_reflection",
            "emotion": wm_emotion_name,  # store just the name
            "timestamp": now,
            "importance": 2,
            "priority": 2,
            "referenced": 1,
            "recall_count": 0,
            "related_memory_id": None,
            "decay": 1.0,
            "tags": ["reflection", "emotion"]
        })
        log_private(f"[emotional reflection - {now}]\n{text}")
        log_reflection(f"Self-belief reflection: {text}")

        # --- Calculate reward parameters dynamically ---
        base_actual_reward = 0.6 + min(0.4, 1.0 - stability)
        modulated_actual_reward = base_actual_reward * (1 - fatigue * 0.4) * (1 + 0.3 * (motivation + excitement))
        modulated_actual_reward = max(0.0, min(modulated_actual_reward, 1.0))

        base_effort = 0.5 + (0.5 if (strongest and all(val < 0.2 for val in emotion_variability)) else 0.0)
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
        release_reward_signal(
            context=context,
            signal_type="dopamine",
            actual_reward=0.1,
            expected_reward=0.7,
            effort=0.6,
            mode="phasic"
        )