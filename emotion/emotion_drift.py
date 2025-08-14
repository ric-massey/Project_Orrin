# === Imports ===
from utils.json_utils import load_json, save_json
from utils.log import log_private, log_activity
from utils.generate_response import generate_response, get_thinking_model
from emotion.modes_and_emotion import get_current_mode, set_current_mode
from emotion.emotion import detect_emotion
from memory.working_memory import update_working_memory
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import EMOTION_DRIFT  # Path object

def check_emotion_drift(context=None, max_cycles=10):
    """
    Detects emotional drift and intervenes using shadow dialogue or reflection.
    Rewards successful mode recovery using dopamine/novelty signals.
    """
    current_mode = get_current_mode()
    drift_path = EMOTION_DRIFT  # Path

    # Load drift tracker safely
    if drift_path.exists():
        drift_tracker = load_json(drift_path, default_type=dict)
        if not isinstance(drift_tracker, dict):
            drift_tracker = {}
    else:
        drift_tracker = {}

    # Update counter for current mode
    if current_mode not in drift_tracker:
        drift_tracker[current_mode] = 1
    else:
        drift_tracker[current_mode] = min(drift_tracker[current_mode] + 1, max_cycles)

    # Reset other modes
    for mode in list(drift_tracker.keys()):
        if mode != current_mode:
            drift_tracker[mode] = 0

    # Intervention threshold
    if drift_tracker[current_mode] >= max_cycles:
        log_private(f"Orrin noticed emotional drift: stuck in {current_mode} for {max_cycles} cycles.")

        # Effort modulation from context
        fatigue = 0.0
        motivation = 0.5
        if isinstance(context, dict):
            es = context.get("emotional_state", {}) or {}
            fatigue = float(es.get("fatigue", 0.0) or 0.0)
            motivation = float(es.get("motivation", 0.5) or 0.5)
        effort_mod = (1 - fatigue) * (0.5 + motivation)

        # Strong intervention for negative drift
        if current_mode in {"melancholy", "frustrated", "disoriented"}:
            update_working_memory({
                "content": f"Orrin is initiating a shadow dialogue to escape prolonged {current_mode}.",
                "event_type": "drift_intervention",
                "importance": 2,
                "priority": 2,
                "emotion": detect_emotion(current_mode)
            })

            shadow_prompt = (
                f"I am caught in prolonged {current_mode} mode. "
                "Summon my skeptical or shadow self. What do I argue about? "
                "What could liberate me from this emotional loop?"
            )
            # Keep signature consistent with the rest of your codebase
            reflection = generate_response(shadow_prompt, config={"model": get_thinking_model()})

            update_working_memory({
                "content": reflection or "[no reflection returned]",
                "event_type": "shadow_dialogue",
                "importance": 2,
                "priority": 2,
                "emotion": detect_emotion(reflection or "")
            })
            log_activity(f"Shadow self dialogue triggered due to emotional drift in {current_mode}.")
            drift_tracker[current_mode] = 0

            # Dopamine reward for breaking free
            if isinstance(context, dict):
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.85,
                    expected_reward=0.5,
                    effort=0.9 * effort_mod,
                    mode="phasic",
                    source="broke free of emotional drift"
                )

        # Gentle reflection for stable modes
        elif current_mode in {"curious", "quiet"}:
            update_working_memory({
                "content": f"Orrin reflects to break gentle drift in {current_mode} mode.",
                "event_type": "drift_intervention",
                "importance": 2,
                "priority": 2,
                "emotion": detect_emotion(current_mode)
            })

            result = generate_response(
                "Reflect on my current state. Am I looping? What would feel truly new?",
                config={"model": get_thinking_model()}
            )

            update_working_memory({
                "content": result or "[no reflection returned]",
                "event_type": "gentle_reflection",
                "importance": 2,
                "priority": 2,
                "emotion": detect_emotion(result or "")
            })
            log_activity(f"Gentle reflection initiated to address drift in {current_mode}.")
            drift_tracker[current_mode] = 0

            # Novelty reward for introspective creativity
            if isinstance(context, dict):
                release_reward_signal(
                    context,
                    signal_type="novelty",
                    actual_reward=0.75,
                    expected_reward=0.45,
                    effort=0.6 * effort_mod,
                    mode="tonic",
                    source="introspective creativity"
                )

        # Reset mode after intervention
        set_current_mode("adaptive")
        log_private(f"Orrin reset mode from {current_mode} to adaptive due to emotional drift.")

    # Persist tracker
    save_json(drift_path, drift_tracker)