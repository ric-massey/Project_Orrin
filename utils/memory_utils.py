from utils.log import log_error

def _safe_str(x) -> str:
    try:
        return (x if isinstance(x, str) else str(x)) or ""
    except Exception:
        return ""

def summarize_memories(memories, limit: int = 10, truncate: int | None = 280) -> str:
    """
    Summarizes the most recent memories, including emotional tone and intensity.
    """
    if not isinstance(memories, list):
        memories = [] if memories is None else list(memories)

    recent = memories[-limit:]
    lines = []

    for m in recent:
        if not isinstance(m, dict):
            lines.append(f"- [INVALID MEMORY: {repr(m)}]")
            continue

        content = _safe_str(m.get("content", "")).strip()
        if truncate and len(content) > truncate:
            content = content[:truncate - 1] + "…"

        # Emotion block: handles dict or flat
        emotion = m.get("emotion")
        if isinstance(emotion, dict):
            emotion_str = _safe_str(emotion.get("emotion"))
            intensity_val = emotion.get("intensity", m.get("intensity"))
        else:
            emotion_str = _safe_str(emotion)
            intensity_val = m.get("intensity")

        # Normalize intensity to float if possible
        intensity = None
        if intensity_val is not None:
            try:
                intensity = round(float(intensity_val), 2)
            except (TypeError, ValueError):
                intensity = None  # ignore unparseable intensity

        event_type = _safe_str(m.get("event_type", ""))
        agent = _safe_str(m.get("agent", ""))

        line = f"- {content}" if content else "-"
        if emotion_str:
            line += f" (felt {emotion_str})"
        if intensity is not None:
            line += f" [intensity: {intensity}]"
        if event_type:
            line += f" {{{event_type}}}"
        if agent and agent != "orrin":
            line += f" <by {agent}>"
        lines.append(line)

    return "\n".join(lines).strip()


def format_memories_for_prompt(memories, include_timestamp: bool = True, truncate: int | None = 220) -> str:
    lines = []
    if not isinstance(memories, list):
        memories = [] if memories is None else list(memories)

    for i, m in enumerate(memories):
        if not isinstance(m, dict):
            log_error(f"[MemoryFormat] Non-dict memory at index {i}: {repr(m)} (type: {type(m)})")
            lines.append(f"- [ERROR: non-dict memory at index {i}: {repr(m)}]")
            continue

        content = _safe_str(m.get("content", ""))
        if truncate and len(content) > truncate:
            content = content[:truncate - 1] + "…"

        event_type = _safe_str(m.get("event_type", "?"))
        s = f"- [{event_type}] {content}"

        emo = m.get("emotion")
        if isinstance(emo, dict):
            em = _safe_str(emo.get("emotion", ""))
            try:
                inten = float(emo.get("intensity", 0))
            except (TypeError, ValueError):
                inten = None
            if em:
                s += f" (felt {em}"
                if inten is not None:
                    s += f", intensity {round(inten, 2)}"
                s += ")"
        elif emo:
            s += f" (felt {_safe_str(emo)})"

        if m.get("importance", 1) and m.get("importance", 1) > 1:
            s += f" [importance: {m.get('importance')}]"
        if m.get("recall_count", 0):
            s += f" [recalled {m.get('recall_count')}x]"
        if include_timestamp and m.get("timestamp"):
            s += f" <{_safe_str(m['timestamp'])}>"

        lines.append(s)
    return "\n".join(lines)