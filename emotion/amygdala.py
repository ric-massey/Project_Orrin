from utils.emotion_utils import dominant_emotion
from utils.generate_response import generate_response
from utils.json_utils import extract_json
from utils.log import log_private

def process_emotional_signals(context):
    """
    Simulates the amygdala's threat detection and shortcut behavior.
    Uses reflection to determine whether a threat exists.
    """

    emotional_state = context.get("emotional_state", {})
    dominant = dominant_emotion(emotional_state)
    context["dominant_emotion"] = dominant

    # Snapshot emotional state for reasoning
    top_emotions = sorted(
        [(k, v) for k, v in emotional_state.items() if isinstance(v, (int, float))],
        key=lambda x: x[1],
        reverse=True
    )[:5]

    emotions_str = "\n".join([f"- {k}: {v:.2f}" for k, v in top_emotions]) or "none"

    # Prompt LLM to evaluate whether threat is active
    prompt = (
        "You are Orrin's amygdala system.\n"
        f"Here is your current emotional state:\n{emotions_str}\n\n"
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

    # Save result
    context["amygdala_response"] = {
        "threat_detected": threat_detected,
        "threat_tags": [response_type] if threat_detected else [],
        "spike_intensity": round(spike_intensity, 2),
        "shortcut_function": shortcut_function,
        "llm_reasoning": data.get("why", "No reason given.")
    }

    return context, context["amygdala_response"]