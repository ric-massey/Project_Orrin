from utils.load_utils import load_json
from datetime import datetime, timezone 
from emotion.emotion import detect_emotion
from utils.json_utils import save_json
from utils.memory_utils import summarize_memories
from selfhood.ethics import update_values_with_lessons
from paths import (
    LONG_MEMORY_FILE, PRIVATE_THOUGHTS_FILE
)

def update_long_memory(
    new,
    emotion=None,
    event_type="summary",
    agent="orrin",
    importance=1,
    priority=1,
    referenced=0,
    pin=False
):
    """
    Add a new long-term memory event.
    """
    memories = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(memories, list):
        memories = []

    if isinstance(new, dict):
        entry = new.copy()
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        entry.setdefault("emotion", emotion or detect_emotion(entry.get("content", "")))
        entry.setdefault("event_type", event_type)
        entry.setdefault("agent", agent)
        entry.setdefault("importance", importance)
        entry.setdefault("priority", priority)
        entry.setdefault("referenced", referenced)
        entry.setdefault("pin", pin)
    elif isinstance(new, str):
        entry = {
            "content": new.strip(),
            "emotion": emotion or detect_emotion(new),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "agent": agent,
            "importance": importance,
            "priority": priority,
            "referenced": referenced,
            "pin": pin
        }
    else:
        return

    memories.append(entry)
    # Optionally call prune here if over your limit
    if len(memories) > 2000:  # or whatever your limit is
        prune_long_memory(max_total=2000)
        # Re-load memories (after pruning, in case you prune by score)
        memories = load_json(LONG_MEMORY_FILE, default_type=list)

    save_json(LONG_MEMORY_FILE, memories)

def reevaluate_memory_significance():
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        return

    for mem in long_memory:
        if not isinstance(mem, dict):
            continue

        content = mem.get("content", "").lower()
        emotion = mem.get("emotion", "neutral")
        score = mem.get("effectiveness_score", 5)

        if "lesson:" in content:
            score = min(score + 1, 10)
        if emotion in ["grief", "joy", "fear", "pride"]:
            score = min(score + 1, 10)

        try:
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(mem["timestamp"])).days
            if age_days > 30 and score > 3:
                score -= 1
        except:
            pass

        mem["effectiveness_score"] = score

    save_json(LONG_MEMORY_FILE, long_memory)

def prune_long_memory(max_total=2000):
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        return

    if len(long_memory) <= max_total:
        return

    def score(mem):
        try:
            score = 0
            emotion = mem.get("emotion", "")
            content = mem.get("content", "").lower()

            strong_emotions = ["joy", "fear", "anger", "grief", "pride", "curiosity"]
            if emotion in strong_emotions:
                score += 3
            if "lesson:" in content:
                score += 4
            score += mem.get("effectiveness_score", 5) // 2

            delta = datetime.now(timezone.utc) - datetime.fromisoformat(mem.get("timestamp", ""))
            days_old = delta.days
            if days_old < 3:
                score += 3
            elif days_old < 7:
                score += 1
            elif days_old > 30:
                score -= 2
        except:
            score = 0
        return score

    scored = sorted(long_memory, key=lambda m: (score(m), m.get("timestamp", "")), reverse=True)
    kept = scored[:max_total]
    removed = scored[max_total:]

    if removed:
        summary = summarize_memories(removed)
        if summary:
            merged = {
                "content": f"🧠 Summary of faded memories:\n{summary}",
                "emotion": detect_emotion(summary),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            kept.append(merged)

        
        update_values_with_lessons()

    save_json(LONG_MEMORY_FILE, kept)

    try:
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Orrin pruned {len(removed)} long memories. "
                    f"{'Summarized and merged.' if removed else ''}\n")
    except:
        pass

def remember(event, context=None):
    if not event:
        return
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    if context:
        entry["context"] = context
    long_memory.append(entry)
    save_json(LONG_MEMORY_FILE, long_memory)