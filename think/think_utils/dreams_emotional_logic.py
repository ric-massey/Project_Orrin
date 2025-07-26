from cognition.dreaming import dream
from emotion.emotion_drift import check_emotion_drift
from behavior.behavior_generation import generate_behavior_from_integration
from emotion.update_emotional_state import  update_emotional_state
from emotion.reflect_on_emotions import reflect_on_emotions
from emotion.apply_emotional_feedback import apply_emotional_feedback
from emotion.amygdala import process_emotional_signals
from memory.working_memory import update_working_memory
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reward_signals.fatigue import update_function_fatigue


def dreams_and_emotional_logic(context):
    """
    Handles dreaming, emotional drift, behavior integration, emotion reflection,
    emotional feedback, amygdala response, and emotional state updating.
    Returns updated context, emotional_state, and amygdala_response.
    """
    cycle_count = context.get("cycle_count", {"count": 0})
    self_model = context.get("self_model", {})
    emotional_state = context.get("emotional_state", {})
    long_memory = context.get("long_memory", [])

    # --- DREAM EVERY 5 CYCLES (not cycle 0) ---
    if cycle_count["count"] % 5 == 0 and cycle_count["count"] > 0:
        dream_text = dream()
        if dream_text:
            update_working_memory({
                "content": "Dream: " + dream_text.strip(),
                "event_type": "dream",
                "importance": 2,
                "priority": 2,
                "referenced": 0,
                "pin": False
            })
            update_function_fatigue(context, "dream")
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=0.4,
                expected_reward=0.3,
                effort=0.3,
                source="dreaming"
            )

    # --- Emotion drift, behavior integration (side effect only) ---
    check_emotion_drift()
    generate_behavior_from_integration(context)

    # --- Reflect on emotions every 10 cycles or if stability drops ---
    if cycle_count["count"] % 10 == 0 or emotional_state.get("emotional_stability", 1.0) < 0.6:
        reflect_on_emotions(context, self_model, long_memory)
        # Optionally add a small reward here if not already rewarded internally

    # --- Apply emotional feedback and amygdala processing ---
    context = apply_emotional_feedback(context)
    context, amygdala_response = process_emotional_signals(context)

    # --- Update emotional state (update context immediately) ---
    update_emotional_state()
    emotional_state = context.get("emotional_state", {})

    return context, emotional_state, amygdala_response