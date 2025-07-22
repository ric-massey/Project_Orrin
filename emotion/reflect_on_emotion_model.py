from datetime import datetime, timezone
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private
from utils.log_reflection import log_reflection
from emotion.reward_signals.reward_signals import release_reward_signal

def reflect_on_emotion_model(context, self_model, memory):
    all_data = load_all_known_json()
    emotion_model = all_data.get("emotion_model", {})

    if not emotion_model:
        update_working_memory("No emotion model available for reflection.")
        return

    summary = "\n".join(
        f"- {emotion}: {', '.join(tags[:3])}..."
        for emotion, tags in emotion_model.items() if isinstance(tags, list)
    )

    context = {
        **all_data,
        "emotion_model": emotion_model,
        "summary": summary,
        "instructions": (
            "These are my defined emotions and their linguistic associations:\n"
            + summary +
            "\n\nReflect on my emotional vocabulary:\n"
            "- Are there overlaps or redundancies?\n"
            "- Are any emotions missing or poorly defined?\n"
            "- Does the vocabulary reflect my lived experience?\n"
            "Suggest updates, additions, or refinements to deepen emotional understanding."
        )
    }

    response = generate_response_from_context(context)

    if response:
        update_working_memory("emotion model reflection: " + response)
        log_private(f"[{datetime.now(timezone.utc)}] Orrin reflected on his emotion model:\n{response}")
        log_reflection(f"Self-belief reflection: {response.strip()}")

        effort = 0.7 if len(emotion_model) > 8 else 0.5
        release_reward_signal(
            context=all_data.get("emotional_state", {}),
            signal_type="dopamine",
            actual_reward=0.65,
            expected_reward=0.5,
            effort=effort,
            mode="phasic"
        )
    else:
        update_working_memory("⚠️ Emotion model reflection failed or returned nothing.")
        release_reward_signal(
            context=all_data.get("emotional_state", {}),
            signal_type="dopamine",
            actual_reward=0.2,
            expected_reward=0.5,
            effort=0.5,
            mode="phasic"
        )