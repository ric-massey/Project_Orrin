from utils.emotion_utils import dominant_emotion
from utils.generate_response import generate_response
from utils.json_utils import extract_json
from utils.log import log_private

def process_emotional_signals(context):
    emotional_state = context.get("emotional_state", {})

    # === Extract core emotions including newer states like fatigue, anxiety, motivation ===
    core = emotional_state.get("core_emotions") or {
        k: v for k, v in emotional_state.items()
        if isinstance(v, (int, float)) and k not in {
            "emotional_stability", "confidence_by_domain", "curiosity", "loneliness"
        }
    }

    dominant = dominant_emotion(emotional_state)
    context["dominant_emotion"] = dominant

    # === Include fatigue and motivation in prompt ===
    fatigue = emotional_state.get("fatigue", 0.0)
    motivation = emotional_state.get("motivation", 0.5)
    dopamine = emotional_state.get("confidence", 0.5)  # or create a dopamine proxy if you want

    # Recent reward spikes (optional, for richer context)
    recent_rewards = context.get("reward_trace", [])[-5:]
    reward_summary = ", ".join(f"{r['type']}({r['strength']:.2f})" for r in recent_rewards) or "none"

    # Snapshot emotional state for reasoning
    top_emotions = sorted(core.items(), key=lambda x: x[1], reverse=True)[:5]
    stability = emotional_state.get("emotional_stability", 1.0)
    emotions_str = "\n".join([f"- {k}: {v:.2f}" for k, v in top_emotions]) or "none"

    # Check for recent novelty/impulse signals that might modulate threat response
    raw_signals = context.get("raw_signals", [])
    recent_impulses = [s for s in raw_signals if s.get("source") == "reward_impulse" and s.get("signal_strength", 0) > 0.8]
    impulses_str = f"{len(recent_impulses)} recent dopamine bursts" if recent_impulses else "no recent bursts"

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
        "\"response_type\": \"fight|flight|freeze|none\", \"why\": \"...\" }"
    )

    result = generate_response(prompt)
    log_private(f"[Amygdala LLM Prompt Response]\n{result}")

    data = extract_json(result)
    if not isinstance(data, dict):
        data = {
            "threat_detected": False,
            "response_type": "none",
            "why": "LLM failed to return usable JSON."
        }

    threat_detected = data.get("threat_detected", False)
    response_type = data.get("response_type", "none")
    spike_intensity = max([v for _, v in top_emotions], default=0.0)

    shortcut_function = {
        "fight": "speak",
        "flight": "dream",
        "freeze": "introspective_planning"
    }.get(response_type, "none")

    # Save extended result with reward/fatigue context for later use
    context["amygdala_response"] = {
        "threat_detected": threat_detected,
        "threat_tags": [response_type] if threat_detected else [],
        "spike_intensity": round(spike_intensity, 2),
        "shortcut_function": shortcut_function,
        "llm_reasoning": data.get("why", "No reason given."),
        "fatigue": fatigue,
        "motivation": motivation,
        "recent_reward_summary": reward_summary,
        "recent_impulses_count": len(recent_impulses)
    }

    return context, context["amygdala_response"]