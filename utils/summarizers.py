# == Imports
from utils.json_utils import load_json
from paths import LONG_MEMORY_FILE 

# == Functions
def summarize_recent_thoughts(n: int = 5, event_type_filter: str = None) -> str:
    """
    Returns a short summary of the most recent reflections (optionally filtered by event_type)
    from long-term memory.
    """
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not long_memory:
        return "No recent thoughts found."

    # Optionally filter by event_type
    if event_type_filter:
        filtered = [item for item in long_memory if isinstance(item, dict) and item.get('event_type') == event_type_filter]
    else:
        filtered = [item for item in long_memory if isinstance(item, dict) and 'content' in item]

    recent = filtered[-n:]

    summary_lines = []
    for item in recent:
        content = item.get('content', '')
        # Unpack emotion if present and dict
        emotion = item.get('emotion')
        if isinstance(emotion, dict):
            emotion_str = emotion.get('emotion')
            intensity = emotion.get('intensity')
        else:
            emotion_str = emotion
            intensity = None
        line = f"- {content}"
        if emotion_str:
            line += f" (felt {emotion_str})"
        if intensity is not None:
            line += f" [intensity: {round(float(intensity),2)}]"
        # Optionally add event_type or timestamp
        # line += f" {{{item.get('event_type', '')}}}"
        summary_lines.append(line)

    return "\n".join(summary_lines) if summary_lines else "No recent thoughts with content."

def summarize_self_model(self_model: dict) -> dict:
    """
    Condenses the full self-model into a lightweight summary for prompting.
    """
    if not isinstance(self_model, dict):
        return {}

    return {
        "core_directive": self_model.get("core_directive", {}).get("statement", "Not found"),
        "core_values": self_model.get("core_values", []),
        "traits": self_model.get("personality_traits", []),
        "identity": self_model.get("identity_story", "An evolving reflective AI"),
        "known_roles": self_model.get("roles", []),
        "recent_focus": self_model.get("recent_focus", [])
    }