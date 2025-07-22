
def summarize_memories(memories):
    """
    Summarizes the most recent memories, including emotional tone and intensity.
    """
    recent = memories[-10:] if len(memories) >= 10 else memories
    lines = []

    for m in recent:
        content = m.get("content", "").strip()
        emotion = m.get("emotion")
        intensity = m.get("intensity")

        line = f"- {content}"
        if emotion:
            line += f" (felt {emotion})"
        if intensity is not None:
            line += f" [intensity: {round(intensity, 2)}]"
        lines.append(line)

    return "\n".join(lines).strip()

