from utils.load_utils import load_json
from utils.json_utils import save_json
from datetime import datetime, timezone 
from utils.log import log_private
from memory.sumarize_w_memory import summarize_and_promote_working_memory

from paths import WORKING_MEMORY_FILE


MAX_WORKING_LOGS = 300

def update_working_memory(
    new,
    emotion=None,
    event_type="thought",
    agent="orrin",
    importance=1,
    priority=1,
    referenced=False,
    pin=False
):
    from emotion.emotion import detect_emotion
    """
    Log an event to working memory.  
    Maintains a short-term, high-priority, self-pruning buffer for immediate context and reasoning.

    Args:
        new (str|dict): Thought or event content.
        emotion (str, optional): Override detected emotion.
        event_type (str): 'thought', 'input', 'response', etc.
        agent (str): Who originated this entry.
        importance (int): Subjective impact (1=default, higher=more important).
        priority (int): For sorting—higher = less likely to prune.
        referenced (bool|int): Was this memory referenced during current reasoning?
        pin (bool): If True, cannot be pruned.
    """
    memories = load_json(WORKING_MEMORY_FILE, default_type=list)
    if not isinstance(memories, list):
        memories = []

    # ---- 1. Create Entry ----
    if isinstance(new, dict):
        entry = new.copy()
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        entry.setdefault("emotion", emotion or detect_emotion(entry.get("content", "")))
        entry.setdefault("event_type", event_type)
        entry.setdefault("agent", agent)
        entry.setdefault("importance", importance)
        entry.setdefault("priority", priority)
        entry.setdefault("referenced", entry.get("referenced", 1 if referenced else 0))
        entry.setdefault("pin", pin)
        entry.setdefault("decay", entry.get("decay", 1.0))
    elif isinstance(new, str):
        entry = {
            "content": new.strip(),
            "emotion": emotion or detect_emotion(new),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "agent": agent,
            "importance": importance,
            "priority": priority,
            "referenced": 1 if referenced else 0,
            "pin": pin,
            "decay": 1.0
        }
    else:
        return

    # ---- 2. Update Reference/Decay ----
    for m in memories:
        if not m.get("pin", False):
            m["decay"] = max(0.0, m.get("decay", 1.0) - 0.02)
        # Boost ref count/decay if referenced (by text match; can be fuzzy in future)
        if m.get("content", "") == entry.get("content", ""):
            m["referenced"] = m.get("referenced", 0) + entry.get("referenced", 0)
            m["decay"] = min(1.0, m.get("decay", 1.0) + 0.1)

    # ---- 3. Append and Pin Deduplication ----
    # Remove duplicates if same pin/content before append (no double pins)
    if entry.get("pin", False):
        memories = [
            m for m in memories
            if not (m.get("pin", False) and m.get("content", "") == entry.get("content", ""))
        ]
    memories.append(entry)

    # ---- 4. Sorting: Pins First, Then Priority/Importance/Decay ----
    # Pin==True sorts first, then priority, importance, decay, then recent
    memories = sorted(
        memories,
        key=lambda m: (
            m.get("pin", False),
            m.get("priority", 1),
            m.get("importance", 1),
            m.get("decay", 1.0),
            m.get("timestamp", ""),
        ),
        reverse=True
    )

    # ---- 5. Pruning (but keep all pins!) ----
    if len(memories) > MAX_WORKING_LOGS:
        # Pins are not dropped—can temporarily exceed MAX_WORKING_LOGS by pin count
        pins = [m for m in memories if m.get("pin", False)]
        non_pins = [m for m in memories if not m.get("pin", False)]
        dropped = non_pins[MAX_WORKING_LOGS - len(pins):]
        kept = non_pins[:MAX_WORKING_LOGS - len(pins)] + pins

        if dropped:
            summarize_and_promote_working_memory(dropped)  # Summarize dropped memories to long-term
            log_private(f"[working_memory] Promoted {len(dropped)} old entries to long-term memory summary.")  # For demo/logging

        # Reassemble (pins always at end in chronological sort)
        memories = kept + pins

    # ---- 6. Optional Final Chronological Sort (if needed for replay/debug) ----
    memories = sorted(memories, key=lambda m: m.get("timestamp", ""))

    save_json(WORKING_MEMORY_FILE, memories)


