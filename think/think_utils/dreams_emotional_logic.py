from cognition.dreaming import dream
from emotion.emotion_drift import check_emotion_drift
from cognition.behavior import generate_behavior_from_integration
from emotion.emotion import reflect_on_emotions, update_emotional_state
from emotion.apply_emotional_feedback import apply_emotional_feedback
from emotion.amygdala import process_emotional_signals
from memory.working_memory import update_working_memory
from utils.json_utils import save_json
from paths import CYCLE_COUNT_FILE

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

    # Increment cycle
    cycle_count["count"] += 1
    save_json(CYCLE_COUNT_FILE, cycle_count)
    context["cycle_count"] = cycle_count

    # --- DREAM EVERY 5 CYCLES ---
    if cycle_count["count"] % 5 == 0:
        dream_text = dream()
        if dream_text:
            update_working_memory("Dream: " + dream_text.strip())

    # --- Emotion drift, behavior generation ---
    check_emotion_drift()
    generate_behavior_from_integration()

    # --- Reflect on emotions every 10 cycles or if stability drops ---
    if cycle_count["count"] % 10 == 0 or emotional_state.get("emotional_stability", 1.0) < 0.6:
        reflect_on_emotions(context, self_model, long_memory)

    # --- Apply emotional feedback and amygdala processing ---
    context = apply_emotional_feedback(context)
    context, amygdala_response = process_emotional_signals(context)

    # --- Update emotional state ---
    update_emotional_state()
    emotional_state = context.get("emotional_state", emotional_state)

    # Return all updated pieces for use elsewhere in main loop
    return context, emotional_state, amygdala_response