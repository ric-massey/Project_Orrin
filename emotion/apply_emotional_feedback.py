# apply_emotional_feedback.py
from datetime import datetime, timezone
from utils.emotion_utils import log_pain, log_uncertainty_spike 
from emotion.update_emotional_state import update_emotional_state
from emotion.modes_and_emotion import set_current_mode
from emotion.emotion_drift import check_emotion_drift
from emotion.reward_signals.reward_signals import release_reward_signal

def _parse_iso_ts(ts: str) -> datetime:
    """Robust ISO8601 parser that tolerates 'Z' and returns aware UTC datetimes."""
    if not isinstance(ts, str):
        return datetime.now(timezone.utc)
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def apply_emotional_feedback(context):
    """
    Simulates realistic affective dynamics including domain-specific confidence,
    emotional memory decay, narrative feedback, suppression, and dominant emotion blending.
    Now logs emotional narratives and feedback into working memory for traceability.
    """
    from memory.working_memory import update_working_memory

    emotional_state = context.get("emotional_state", {}) or {}
    cognition_log = context.get("cognition_log", [])[-7:] or []
    feedback_weight = float(context.get("feedback_weight", 1.0) or 1.0)

    # === A. Domain-Specific Confidence Adjustment ===
    confidence_by_domain = dict(emotional_state.get("confidence_by_domain", {}) or {})
    success_tags = {"success", "clarity", "coherence"}
    failure_tags = {"failure", "error", "conflict", "confusion"}
    inertia = 0.85

    for thought in cognition_log:
        if not isinstance(thought, dict):
            continue
        domain = thought.get("domain", "general")
        importance = float(thought.get("importance", 0.5) or 0.5)
        tags = thought.get("tags", []) or []

        valence = 0
        if any(t in success_tags for t in tags):
            valence = 1
        elif any(t in failure_tags for t in tags):
            valence = -1

        intensity = importance * feedback_weight

        if domain not in confidence_by_domain:
            confidence_by_domain[domain] = 0.5

        current_conf = float(confidence_by_domain.get(domain, 0.5))
        delta = 0.1 * (max(0.0, intensity) ** 1.5)

        if valence > 0:
            confidence_by_domain[domain] = min(1.0, (current_conf * inertia) + (delta * (1 - inertia)))
            # Reward for a success event with effort modulated by fatigue and motivation
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.9,
                expected_reward=0.6,
                effort=intensity * (1 - float(emotional_state.get("fatigue", 0.0) or 0.0)) * (0.5 + float(emotional_state.get("motivation", 0.5) or 0.5)),
                mode="phasic",
                source="success event"
            )
            update_working_memory({
                "content": f"Success event in {domain}: tags={tags}, importance={importance}",
                "event_type": "emotion_feedback",
                "tags": tags,
                "importance": importance,
                "domain": domain,
                "valence": valence,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        elif valence < 0:
            log_pain(context, "confusion", increment=delta)
            confidence_by_domain[domain] = max(0.0, (current_conf * inertia) - (delta * 1.2 * (1 - inertia)))
            update_working_memory({
                "content": f"Negative event in {domain}: tags={tags}, importance={importance}",
                "event_type": "emotion_feedback",
                "tags": tags,
                "importance": importance,
                "domain": domain,
                "valence": valence,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    emotional_state["confidence_by_domain"] = confidence_by_domain

    # === B. Emotion Memory Buffer with Decay ===
    emotional_events = context.get("emotional_events", []) or []
    decay_rate = 0.05
    now = datetime.now(timezone.utc)

    # Keep only last hour and only well-formed entries
    filtered_events = []
    for e in emotional_events:
        if not isinstance(e, dict):
            continue
        ts = _parse_iso_ts(e.get("timestamp"))
        if (now - ts).total_seconds() < 3600:
            # ensure valid shape
            emo = e.get("emotion")
            try:
                intensity = float(e.get("intensity", 0.0) or 0.0)
            except Exception:
                intensity = 0.0
            if isinstance(emo, str):
                filtered_events.append({"emotion": emo, "intensity": intensity, "timestamp": ts.isoformat()})
    emotional_events = filtered_events

    mood_influence = {}
    for e in emotional_events:
        ts = _parse_iso_ts(e["timestamp"])
        age_seconds = (now - ts).total_seconds()
        decay = max(0.0, 1 - (decay_rate * age_seconds / 60.0))
        mood_influence[e["emotion"]] = mood_influence.get(e["emotion"], 0.0) + e["intensity"] * decay

    for k, v in mood_influence.items():
        try:
            base = float(emotional_state.get(k, 0.0) or 0.0)
        except Exception:
            base = 0.0
        emotional_state[k] = round(min(1.0, base + v * 0.2), 3)

    context["emotional_events"] = emotional_events

    # === C. Narrative Generation (for self-explanation or logging) ===
    if cognition_log:
        most_impactful = max(cognition_log, key=lambda x: (isinstance(x, dict) and float(x.get("importance", 0.5) or 0.5)) or 0.5)
        tags = (most_impactful.get('tags') or []) if isinstance(most_impactful, dict) else []
        description = (most_impactful.get('description') or 'a recent event') if isinstance(most_impactful, dict) else 'a recent event'
        narrative = f"I felt {' and '.join(tags) if tags else 'something'} during {description}."
        context["emotion_narrative"] = narrative
        update_working_memory({
            "content": narrative,
            "event_type": "emotion_narrative",
            "importance": float(most_impactful.get("importance", 1) or 1) if isinstance(most_impactful, dict) else 1,
            "priority": 2,
            "emotion": tags[0] if tags else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # === D. Sudden Mood Collapse — Trigger Secondary Effects ===
    stability = float(emotional_state.get("emotional_stability", 1.0) or 1.0)
    if stability < 0.35:
        # NOTE: ensure your util is actually named log_uncertainty_spikee; if it's log_uncertainty_spike, update the import.
        log_uncertainty_spike(context, increment=0.2)
    else:
        # Reward when stability remains high, modulated by fatigue and motivation
        release_reward_signal(
            context,
            signal_type="serotonin",
            actual_reward=0.85,
            expected_reward=0.5,
            effort=0.5 * (1 - float(emotional_state.get("fatigue", 0.0) or 0.0)) * (0.5 + float(emotional_state.get("motivation", 0.5) or 0.5)),
            mode="tonic",
            source="stability reward"
        )

    # === E. Suppressed Emotions (based on context) ===
    masked = context.get("mask_emotions", []) or []
    for emotion in masked:
        if isinstance(emotion, str) and isinstance(emotional_state.get(emotion), (int, float)):
            emotional_state[emotion] = float(emotional_state[emotion]) * 0.5  # dampen

    # === F. Dominant Emotion Blending ===
    # Include numeric emotions only; exclude meta keys.
    numeric_emotions = {
        k: float(v)
        for k, v in emotional_state.items()
        if isinstance(v, (int, float)) and k not in {"confidence", "emotional_stability"}
    }
    top_two = sorted(numeric_emotions.items(), key=lambda x: x[1], reverse=True)[:2]
    context["dominant_emotions"] = [e[0] for e in top_two]

    if top_two:
        set_current_mode(top_two[0][0])  # Still pick the top one for mode
        # Reward emotional clarity if top emotions are strongly defined
        if top_two[0][1] > 0.7:
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=float(top_two[0][1]),
                expected_reward=0.5,
                effort=0.6 * (1 - float(emotional_state.get("fatigue", 0.0) or 0.0)) * (0.5 + float(emotional_state.get("motivation", 0.5) or 0.5)),
                mode="tonic",
                source="emotional clarity"
            )
            update_working_memory({
                "content": f"Strongly defined dominant emotion: {top_two[0][0]} ({top_two[0][1]:.2f})",
                "event_type": "dominant_emotion",
                "emotion": top_two[0][0],
                "intensity": float(top_two[0][1]),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    # === G. Drift + Update Final State ===
    check_emotion_drift(max_cycles=10)
    update_emotional_state()
    return context