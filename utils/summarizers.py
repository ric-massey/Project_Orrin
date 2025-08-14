# == Imports
from __future__ import annotations

from typing import Optional, Dict, Any, List
from utils.json_utils import load_json
from paths import LONG_MEMORY_FILE

# == Functions
def summarize_recent_thoughts(n: int = 5, event_type_filter: Optional[str] = None) -> str:
    """
    Return a short summary of the most recent long-memory entries (optionally filtered by event_type).
    Most recent entries appear first. If no entries, returns a friendly message.
    """
    if not isinstance(n, int) or n <= 0:
        n = 5

    long_memory: List[Dict[str, Any]] = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list) or not long_memory:
        return "No recent thoughts found."

    # Filter to dict entries with content
    if event_type_filter:
        filtered = [m for m in long_memory if isinstance(m, dict) and m.get("event_type") == event_type_filter and "content" in m]
    else:
        filtered = [m for m in long_memory if isinstance(m, dict) and "content" in m]

    if not filtered:
        return "No recent thoughts with content."

    # Take last n (most recent), then reverse to show newest first
    recent = list(reversed(filtered[-n:]))

    lines: List[str] = []
    for m in recent:
        content = m.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()

        # Emotion can be a dict or a string
        emo = m.get("emotion")
        intensity = None
        if isinstance(emo, dict):
            emotion_str = emo.get("emotion")
            intensity = emo.get("intensity")
        else:
            emotion_str = emo

        line = f"- {content}"
        if emotion_str:
            line += f" (felt {emotion_str})"
        try:
            if intensity is not None:
                line += f" [intensity: {round(float(intensity), 2)}]"
        except (TypeError, ValueError):
            # skip bad intensity values silently
            pass

        # If you ever want timestamps or event_type, uncomment:
        # ts = m.get("timestamp", "")
        # et = m.get("event_type", "")
        # if et: line += f" {{{et}}}"
        # if ts: line += f" @ {ts}"

        lines.append(line)

    return "\n".join(lines)


def summarize_self_model(self_model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Condense the self model into a lightweight dict for prompting.
    Uses canonical keys used elsewhere in the codebase.
    """
    if not isinstance(self_model, dict):
        return {}

    core_dir = self_model.get("core_directive", {})
    if isinstance(core_dir, str):
        core_statement = core_dir or "Not found"
    else:
        core_statement = core_dir.get("statement", "Not found")

    return {
        "core_directive": core_statement,
        "core_values": self_model.get("core_values", []),
        "traits": self_model.get("traits", []),                # <- canonical key
        "identity": self_model.get("identity", "An evolving reflective AI"),
        "known_roles": self_model.get("known_roles", []),      # <- canonical key
        "recent_focus": self_model.get("recent_focus", []),
    }