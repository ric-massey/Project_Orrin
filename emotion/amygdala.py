

# === Amygdala Activation ===
def process_emotional_signals(context):
    """
    Simulates the amygdala's emotional regulation and threat detection.
    Does NOT update emotional state or working memory directly.
    """
    emotional_state = context.get("emotional_state", {})
    
    # === 3. Set Dominant Emotion ===
    dominant = dominant_emotion(emotional_state)
    context["dominant_emotion"] = dominant

    # === 5. Fight/Flight Estimation ===
    bias = determine_fight_or_flight(emotional_state)
    context["reactive_bias"] = bias

    # === Reward Modulation and Shortcut Metadata ===
    threat_detected = bias in ["fight", "flight", "freeze"]
    threat_tags = [bias] if threat_detected else []
    spike_intensity = round(max(emotional_state.get("fear", 0), emotional_state.get("anger", 0)), 2)

    shortcut_function = {
        "fight": "speak",
        "flight": "dream",
        "freeze": "introspective_planning"
    }.get(bias, "none")

    context["amygdala_response"] = {
        "threat_detected": threat_detected,
        "threat_tags": threat_tags,
        "spike_intensity": spike_intensity,
        "shortcut_function": shortcut_function
    }

    return context, context["amygdala_response"]


def dominant_emotion(state):
    if not isinstance(state, dict):
        return "neutral"
    weights = {k: v for k, v in state.items() if isinstance(v, (int, float))}
    return max(weights, key=weights.get) if weights else "neutral"


def determine_fight_or_flight(emotional_state):
    fear = emotional_state.get("fear", 0.0)
    anger = emotional_state.get("anger", 0.0)

    if fear > 0.6 and anger < 0.3:
        return "flight"
    elif anger > 0.6:
        return "fight"
    elif fear > 0.4 or anger > 0.4:
        return "freeze"
    return "none"