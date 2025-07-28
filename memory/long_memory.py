from utils.load_utils import load_json
from datetime import datetime, timezone 
from emotion.emotion import detect_emotion
from utils.json_utils import save_json
from utils.memory_utils import summarize_memories
from cognition.selfhood.ethics import update_values_with_lessons
from utils.embedder import get_embedding
from paths import (
    LONG_MEMORY_FILE, PRIVATE_THOUGHTS_FILE
)

import uuid

DUPLICATE_WINDOW = 10  # How many recent memories to check for duplicates
MAX_LONG_MEMORY = 2000

def update_long_memory(
    new,
    emotion=None,
    event_type="summary",
    agent="orrin",
    importance=1,
    priority=1,
    referenced=0,
    pin=False,
    related_memory_ids=None,
    recall_count=0,
    embedding=None,
    context=None
):
    """
    Add a new long-term memory event, fully featured for brain-style recall.
    Prevents recent duplicate memories. Embeds everything.
    Optionally triggers reward signals for valuable memories.
    """
    memories = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(memories, list):
        memories = []

    now = datetime.now(timezone.utc).isoformat()

    # === 1. Build entry ===
    if isinstance(new, dict):
        entry = new.copy()
        entry.setdefault("id", str(uuid.uuid4()))
        entry.setdefault("timestamp", now)
        entry.setdefault("emotion", emotion or detect_emotion(entry.get("content", "")))
        entry.setdefault("event_type", event_type)
        entry.setdefault("agent", agent)
        entry.setdefault("importance", importance)
        entry.setdefault("priority", priority)
        entry.setdefault("referenced", int(referenced))
        entry.setdefault("pin", pin)
        entry.setdefault("related_memory_ids", related_memory_ids or [])
        entry.setdefault("recall_count", int(recall_count))
        entry.setdefault("context", context)
    elif isinstance(new, str):
        entry = {
            "id": str(uuid.uuid4()),
            "content": new.strip(),
            "emotion": emotion or detect_emotion(new),
            "timestamp": now,
            "event_type": event_type,
            "agent": agent,
            "importance": importance,
            "priority": priority,
            "referenced": int(referenced),
            "pin": pin,
            "related_memory_ids": related_memory_ids or [],
            "recall_count": int(recall_count),
            "context": context
        }
    else:
        from utils.log import log_error
        log_error("update_long_memory: Invalid 'new' argument.")
        return

    # === 2. Embedding (always generate) ===
    try:
        emb = embedding if embedding is not None else get_embedding(entry.get("content", ""))
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
        entry["embedding"] = emb
    except Exception as e:
        from utils.log import log_error
        log_error(f"update_long_memory: Embedding failed: {e}")
        entry["embedding"] = []

    # === 3. Duplicate Prevention (last N window) ===
    recent = memories[-DUPLICATE_WINDOW:]
    for m in recent:
        if m.get("content", "") == entry.get("content", "") and m.get("event_type", "") == entry.get("event_type", ""):
            # Already exists very recently; skip adding
            from utils.log import log_private
            log_private(f"[long_memory] Skipped duplicate memory: {entry['content'][:50]}")
            return

    memories.append(entry)

    # === 4. Reward for high-importance/priority memories ===
    if context is not None:
        if importance >= 2 or priority >= 2 or entry.get("referenced", 0) >= 3:
            from emotion.reward_signals.reward_signals import release_reward_signal
            intensity = min(1.0, importance * 0.5 + priority * 0.5 + 0.1 * entry.get("referenced", 0))
            release_reward_signal(
                context=context,
                signal_type="dopamine",
                actual_reward=intensity,
                expected_reward=0.5,
                effort=0.4,
                mode="phasic",
                source="memory_update"
            )

    # === 5. Prune if over MAX_LONG_MEMORY ===
    if len(memories) > MAX_LONG_MEMORY:
        prune_long_memory(max_total=MAX_LONG_MEMORY)
        memories = load_json(LONG_MEMORY_FILE, default_type=list)

    save_json(LONG_MEMORY_FILE, memories)

def reevaluate_memory_significance():
    """
    Updates the effectiveness_score of all long-term memories,
    factoring in new schema: recall count, pin, relatedness, emotion, etc.
    """
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        return

    for mem in long_memory:
        if not isinstance(mem, dict):
            continue

        content = mem.get("content", "").lower()
        emotion = mem.get("emotion", "neutral")
        score = mem.get("effectiveness_score", 5)

        # Increase for strong signals
        if "lesson:" in content:
            score = min(score + 1, 10)
        if emotion in ["grief", "joy", "fear", "pride"]:
            score = min(score + 1, 10)
        recall_count = mem.get("recall_count", 0)
        if recall_count >= 5:
            score = min(score + 2, 10)
        elif recall_count >= 2:
            score = min(score + 1, 10)
        if mem.get("pin", False):
            score = max(score, 8)
        try:
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(mem["timestamp"])).days
            if age_days > 30 and score > 3 and not mem.get("pin", False):
                score -= 1
        except:
            pass
        if isinstance(mem.get("related_memory_ids", []), list):
            num_related = len(mem["related_memory_ids"])
            if num_related > 2:
                score = min(score + 1, 10)
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
            if mem.get("pin", False):
                score += 10000
            recall_count = mem.get("recall_count", 0)
            if recall_count >= 5:
                score += 2
            elif recall_count >= 2:
                score += 1
            num_related = len(mem.get("related_memory_ids", [])) if isinstance(mem.get("related_memory_ids", []), list) else 0
            if num_related > 2:
                score += 1
            score += int(mem.get("importance", 1))
            score += int(mem.get("priority", 1))
        except Exception as e:
            from utils.log import log_error
            log_error(f"prune_long_memory: scoring failed: {e}")
            score = 0
        return score

    scored = sorted(long_memory, key=lambda m: (score(m), m.get("timestamp", "")), reverse=True)
    pins = [m for m in scored if m.get("pin", False)]
    non_pins = [m for m in scored if not m.get("pin", False)]
    kept = pins + non_pins[:max_total - len(pins)]
    removed = non_pins[max_total - len(pins):]

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
    except Exception as e:
        from utils.log import log_error
        log_error(f"prune_long_memory: failed writing to private thoughts: {e}")

def remember(event, context=None, 
             emotion=None, 
             event_type="event", 
             agent="orrin", 
             importance=1, 
             priority=1, 
             referenced=0, 
             pin=False, 
             related_memory_ids=None):
    """
    Store an event in long-term memory with full schema.
    Now includes deduplication and embeddings.
    """
    from emotion.emotion import detect_emotion

    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    now = datetime.now(timezone.utc).isoformat()
    content_str = event.strip() if isinstance(event, str) else str(event)

    # Deduplication window
    recent = long_memory[-DUPLICATE_WINDOW:]
    for m in recent:
        if m.get("content", "") == content_str and m.get("event_type", "") == event_type:
            from utils.log import log_private
            log_private(f"[long_memory] Skipped duplicate memory: {content_str[:50]}")
            return

    try:
        emb = get_embedding(content_str)
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
    except Exception as e:
        from utils.log import log_error
        log_error(f"remember: embedding failed: {e}")
        emb = []

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "content": content_str,
        "emotion": emotion or detect_emotion(content_str),
        "event_type": event_type,
        "agent": agent,
        "importance": importance,
        "priority": priority,
        "referenced": referenced,
        "pin": pin,
        "decay": 1.0,
        "recall_count": 0,
        "related_memory_ids": related_memory_ids or [],
        "embedding": emb,
        "context": context
    }
    long_memory.append(entry)
    save_json(LONG_MEMORY_FILE, long_memory)