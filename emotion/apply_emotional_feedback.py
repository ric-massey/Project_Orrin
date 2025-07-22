
from datetime import datetime, timezone
from utils.emotion_utils import log_pain, log_uncertainty_spike
from emotion.emotion import update_emotional_state
from emotion.modes_and_emotion import set_current_mode
from emotion.emotion_drift import check_emotion_drift
from emotion.reward_signals.reward_signals import release_reward_signal

def apply_emotional_feedback(context):
    """
    Simulates realistic affective dynamics including domain-specific confidence,
    emotional memory decay, narrative feedback, suppression, and dominant emotion blending.
    """
    emotional_state = context.get("emotional_state", {})
    cognition_log = context.get("cognition_log", [])[-7:]
    feedback_weight = context.get("feedback_weight", 1.0)

    # === A. Domain-Specific Confidence Adjustment ===
    confidence_by_domain = emotional_state.get("confidence_by_domain", {})
    success_tags = ["success", "clarity", "coherence"]
    failure_tags = ["failure", "error", "conflict", "confusion"]
    inertia = 0.85

    for thought in cognition_log:
        domain = thought.get("domain", "general")
        importance = thought.get("importance", 0.5)
        tags = thought.get("tags", [])
        valence = 1 if any(tag in success_tags for tag in tags) else -1 if any(tag in failure_tags for tag in tags) else 0
        intensity = importance * feedback_weight

        if domain not in confidence_by_domain:
            confidence_by_domain[domain] = 0.5

        current_conf = confidence_by_domain[domain]
        delta = 0.1 * (intensity ** 1.5)

        if valence > 0:
            confidence_by_domain[domain] = min(1.0, (current_conf * inertia) + (delta * (1 - inertia)))
            # ✅ Reward for a success event
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.9,
                expected_reward=0.6,
                effort=intensity,
                mode="phasic"
            )
        elif valence < 0:
            log_pain(context, "confusion", increment=delta)
            confidence_by_domain[domain] = max(0.0, (current_conf * inertia) - (delta * 1.2 * (1 - inertia)))

    emotional_state["confidence_by_domain"] = confidence_by_domain

    # === B. Emotion Memory Buffer with Decay ===
    emotional_events = context.get("emotional_events", [])
    decay_rate = 0.05
    now = datetime.now(timezone.utc)

    emotional_events = [
        e for e in emotional_events
        if (now - datetime.fromisoformat(e["timestamp"])).total_seconds() < 3600  # 1 hour window
    ]

    mood_influence = {}
    for e in emotional_events:
        age_seconds = (now - datetime.fromisoformat(e["timestamp"])).total_seconds()
        decay = max(0, 1 - (decay_rate * age_seconds / 60))
        mood_influence[e["emotion"]] = mood_influence.get(e["emotion"], 0) + e["intensity"] * decay

    for k, v in mood_influence.items():
        emotional_state[k] = round(min(1.0, emotional_state.get(k, 0.0) + v * 0.2), 3)

    context["emotional_events"] = emotional_events

    # === C. Narrative Generation (for self-explanation or logging) ===
    if cognition_log:
        most_impactful = max(cognition_log, key=lambda x: x.get("importance", 0.5))
        context["emotion_narrative"] = f"I felt {' and '.join(most_impactful.get('tags', []))} during {most_impactful.get('description', 'a recent event')}."

    # === D. Sudden Mood Collapse — Trigger Secondary Effects ===
    if emotional_state.get("emotional_stability", 1.0) < 0.35:
        log_uncertainty_spike(context, increment=0.2)
    else:
        # ✅ Reward when stability remains high
        release_reward_signal(
            context,
            signal_type="serotonin",
            actual_reward=0.85,
            expected_reward=0.5,
            effort=0.5
        )

    # === E. Suppressed Emotions (based on context) ===
    masked = context.get("mask_emotions", [])
    for emotion in masked:
        if emotion in emotional_state:
            emotional_state[emotion] *= 0.5  # dampen

    # === F. Dominant Emotion Blending ===
    top_two = sorted(
        {k: v for k, v in emotional_state.items() if isinstance(v, float) and k not in ["confidence", "emotional_stability"]}.items(),
        key=lambda x: x[1],
        reverse=True
    )[:2]
    context["dominant_emotions"] = [e[0] for e in top_two]

    if top_two:
        set_current_mode(top_two[0][0])  # Still pick the top one for mode
        # ✅ Reward emotional clarity if top emotions are strongly defined
        if top_two[0][1] > 0.7:
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=top_two[0][1],
                expected_reward=0.5,
                effort=0.6
            )

    # === G. Drift + Update Final State ===
    check_emotion_drift(max_cycles=10)
    update_emotional_state()
    return context