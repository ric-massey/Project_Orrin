# amygdala.py
from utils.emotion_utils import dominant_emotion
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json
from utils.log import log_activity

def process_emotional_signals(context):
    emotional_state = context.get("emotional_state", {}) or {}

    # === Extract core emotions (only numeric values) ===
    if isinstance(emotional_state.get("core_emotions"), dict):
        core = {k: float(v) for k, v in emotional_state["core_emotions"].items()
                if isinstance(v, (int, float))}
    else:
        core = {k: float(v) for k, v in emotional_state.items()
                if isinstance(v, (int, float)) and k not in {
                    "emotional_stability", "confidence_by_domain", "curiosity", "loneliness"
                }}

    # Dominant emotion (fallback to 'neutral')
    try:
        dom = dominant_emotion(emotional_state)
    except Exception:
        dom = "neutral"
    context["dominant_emotion"] = dom or "neutral"

    # Scalar snapshots for prompt
    fatigue    = float(emotional_state.get("fatigue", 0.0) or 0.0)
    motivation = float(emotional_state.get("motivation", 0.5) or 0.5)
    dopamine   = float(emotional_state.get("confidence", 0.5) or 0.5)  # proxy
    stability  = float(emotional_state.get("emotional_stability", 1.0) or 1.0)

    # Recent reward spikes (defensive)
    recent_rewards = context.get("reward_trace", []) or []
    summary_bits = []
    for r in recent_rewards[-5:]:
        if isinstance(r, dict):
            rtype = str(r.get("type", "unknown"))
            try:
                rstr = float(r.get("strength", 0.0) or 0.0)
            except Exception:
                rstr = 0.0
            summary_bits.append(f"{rtype}({rstr:.2f})")
    reward_summary = ", ".join(summary_bits) if summary_bits else "none"

    # Novelty/impulse signals
    raw_signals = context.get("raw_signals", []) or []
    recent_impulses = [
        s for s in raw_signals
        if isinstance(s, dict) and s.get("source") == "reward_impulse" and (s.get("signal_strength", 0) or 0) > 0.8
    ]
    impulses_str = f"{len(recent_impulses)} recent dopamine bursts" if recent_impulses else "no recent bursts"

    # Top emotions preview (up to 5)
    top_emotions = sorted(core.items(), key=lambda x: x[1], reverse=True)[:5]
    emotions_str = "\n".join(f"- {k}: {v:.2f}" for k, v in top_emotions) if top_emotions else "none"

    prompt = (
        "You are Orrin's amygdala system.\n"
        f"Current emotional state:\n{emotions_str}\n\n"
        f"Emotional stability: {stability:.2f}\n"
        f"Fatigue level: {fatigue:.2f}\n"
        f"Motivation level: {motivation:.2f}\n"
        f"Dopamine proxy: {dopamine:.2f}\n"
        f"Recent reward spikes: {reward_summary}\n"
        f"Novelty/impulse signals: {impulses_str}\n\n"
        "Does this reflect a significant threat requiring reflexive action?\n"
        "If so, classify it as fight, flight, freeze, or none.\n"
        "Respond as JSON: { \"threat_detected\": true/false, "
        "\"response_type\": \"fight|flight|freeze|none\", \"why\": \"\" }"
    )

    result = generate_response(prompt, config={"model": get_thinking_model()})
    log_activity(f"[Amygdala LLM Prompt Response]\n{result}")

    data = extract_json(result)
    if not isinstance(data, dict):
        data = {}

    # Normalize parsed result
    threat_detected = bool(data.get("threat_detected", False))
    response_type = str(data.get("response_type", "none") or "none").lower()
    if response_type not in {"fight", "flight", "freeze", "none"}:
        response_type = "none"

    why = str(data.get("why", "No reason given."))

    # Compute spike_intensity from top emotions safely
    spike_intensity = max((v for _, v in top_emotions), default=0.0)

    shortcut_map = {
        "fight": "speak",
        "flight": "dream",
        "freeze": "introspective_planning",
        "none": "none",
    }
    shortcut_function = shortcut_map[response_type] if threat_detected else "none"

    # Save extended result with reward/fatigue context
    context["amygdala_response"] = {
        "threat_detected": threat_detected,
        "threat_tags": [response_type] if threat_detected else [],
        "spike_intensity": round(float(spike_intensity or 0.0), 2),
        "shortcut_function": shortcut_function,
        "llm_reasoning": why,
        "fatigue": fatigue,
        "motivation": motivation,
        "recent_reward_summary": reward_summary,
        "recent_impulses_count": len(recent_impulses),
    }

    return context, context["amygdala_response"]