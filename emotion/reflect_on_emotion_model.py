from datetime import datetime, timezone
from utils.load_utils import load_all_known_json
from utils.response_utils import generate_response_from_context
from memory.working_memory import update_working_memory
from utils.log import log_private
from utils.log_reflection import log_reflection
from emotion.reward_signals.reward_signals import release_reward_signal

def reflect_on_emotion_model(context, self_model, memory):
    """
    Reflect on the current emotion model and optionally trigger reward signals.
    - Uses load_all_known_json() to fetch the latest emotion model.
    - Logs a concise summary to working memory.
    - Rewards successful reflection; smaller reward on failure.
    """
    in_ctx = context or {}  # keep caller's context intact
    all_data = load_all_known_json()
    emotion_model = all_data.get("emotion_model", {})

    # No emotion model found
    if not isinstance(emotion_model, dict) or not emotion_model:
        update_working_memory({
            "content": "No emotion model available for reflection.",
            "event_type": "system",
            "importance": 1,
            "priority": 1,
            "agent": "orrin",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return

    # Build a brief summary (first 3 tags per emotion)
    lines = []
    for emotion, tags in emotion_model.items():
        if isinstance(tags, list):
            sample = ", ".join(str(t) for t in tags[:3])
            lines.append(f"- {emotion}: {sample}")
    summary = "\n".join(lines)

    # Build LLM prompt context separately (don’t overwrite caller context)
    prompt_ctx = {
        **all_data,
        "emotion_model": emotion_model,
        "summary": summary,
        "instructions": (
            "These are my defined emotions and their linguistic associations:\n"
            f"{summary}\n\n"
            "Reflect on my emotional vocabulary:\n"
            "- Are there overlaps or redundancies?\n"
            "- Are any emotions missing or poorly defined?\n"
            "- Does the vocabulary reflect my lived experience?\n"
            "Suggest updates, additions, or refinements to deepen emotional understanding."
        )
    }

    try:
        response = generate_response_from_context(prompt_ctx)
    except Exception:
        response = None

    ts = datetime.now(timezone.utc).isoformat()

    if isinstance(response, str) and response.strip():
        text = response.strip()

        update_working_memory({
            "content": "emotion model reflection: " + text,
            "event_type": "emotion_model_reflection",
            "importance": 2,
            "priority": 2,
            "agent": "orrin",
            "timestamp": ts
        })

        log_private(f"[{ts}] Orrin reflected on his emotion model:\n{text}")
        log_reflection(f"Self-belief reflection: {text}")

        # Reward sizing: a bit larger effort if the vocabulary is richer
        effort = 0.7 if len(emotion_model) > 8 else 0.5
        release_reward_signal(
            context=in_ctx,          # use caller's context so traces accumulate
            signal_type="dopamine",
            actual_reward=0.65,
            expected_reward=0.5,
            effort=effort,
            mode="phasic"
        )
    else:
        update_working_memory({
            "content": "⚠️ Emotion model reflection failed or returned nothing.",
            "event_type": "emotion_model_reflection",
            "importance": 1,
            "priority": 1,
            "agent": "orrin",
            "timestamp": ts
        })
        release_reward_signal(
            context=in_ctx,
            signal_type="dopamine",
            actual_reward=0.2,
            expected_reward=0.5,
            effort=0.5,
            mode="phasic"
        )