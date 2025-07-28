from utils.log import log_error

def summarize_memories(memories):
    """
    Summarizes the most recent memories, including emotional tone and intensity.
    """
    recent = memories[-10:] if len(memories) >= 10 else memories
    lines = []

    for m in recent:
        content = m.get("content", "").strip()
        # Emotion block: handles dict or flat
        emotion = m.get("emotion")
        if isinstance(emotion, dict):
            emotion_str = emotion.get("emotion")
            intensity = emotion.get("intensity")
        else:
            emotion_str = emotion
            intensity = m.get("intensity")
        # Add more tags if wanted
        event_type = m.get("event_type", "")
        agent = m.get("agent", "")
        line = f"- {content}"
        if emotion_str:
            line += f" (felt {emotion_str})"
        if intensity is not None:
            line += f" [intensity: {round(float(intensity), 2)}]"
        if event_type:
            line += f" {{{event_type}}}"
        if agent and agent != "orrin":
            line += f" <by {agent}>"
        lines.append(line)

    return "\n".join(lines).strip()

def format_memories_for_prompt(memories):
    lines = []
    for i, m in enumerate(memories):
        if not isinstance(m, dict):
            log_error(f"[MemoryFormat] Non-dict memory at index {i}: {repr(m)} (type: {type(m)})")
            lines.append(f"- [ERROR: non-dict memory at index {i}: {repr(m)}]")
            continue

        # Add event_type, importance, emotion, timestamp for richer context
        s = f"- [{m.get('event_type', '?')}] {m.get('content', '')}"
        if m.get("emotion"):
            if isinstance(m["emotion"], dict):
                em = m["emotion"].get("emotion", "")
                intensity = m["emotion"].get("intensity", 0)
                if em:
                    s += f" (felt {em}, intensity {intensity})"
            else:
                s += f" (felt {m['emotion']})"
        if m.get("importance", 1) > 1:
            s += f" [importance: {m.get('importance')}]"
        if m.get("recall_count", 0) > 0:
            s += f" [recalled {m['recall_count']}x]"
        lines.append(s)
    return "\n".join(lines)