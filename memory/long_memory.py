from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import uuid

from cognition.selfhood.ethics import update_values_with_lessons
from emotion.emotion import detect_emotion
from paths import LONG_MEMORY_FILE, PRIVATE_THOUGHTS_FILE
from utils.embedder import get_embedding
from utils.json_utils import save_json
from utils.load_utils import load_json
from utils.log import log_error, log_private
from utils.memory_utils import summarize_memories

# Constants defining behaviour
DUPLICATE_WINDOW: int = 10        # Number of recent entries to check for duplicates
MAX_LONG_MEMORY: int = 2000       # Maximum allowed entries in long-term memory
STRONG_EMOTIONS = {"joy", "fear", "anger", "grief", "pride", "curiosity"}


def update_long_memory(
    new: Any,
    emotion: Optional[str] = None,
    event_type: str = "summary",
    agent: str = "orrin",
    importance: int = 1,
    priority: int = 1,
    referenced: int = 0,
    pin: bool = False,
    related_memory_ids: Optional[List[str]] = None,
    recall_count: int = 0,
    embedding: Optional[List[float]] = None,
    context: Optional[dict] = None,
) -> None:
    """Append a new event to long-term memory, with duplicate prevention and embedding generation.

    Args:
        new: Either a string representing the content or a dict with existing fields.
        emotion: Optional override for the detected emotion.
        event_type: Category of the event (e.g. "summary", "event").
        agent: Identifier for the agent that generated the memory.
        importance: Subjective importance level.
        priority: Priority level for retrieval.
        referenced: Number of references to this memory at creation.
        pin: If True, prevents the entry from being pruned.
        related_memory_ids: IDs of related memories.
        recall_count: Initial recall count.
        embedding: Precomputed embedding vector; if None, one is generated.
        context: Optional context object used to trigger reward signals.

    Errors are logged via log_error; the function does not raise.
    """
    # Load existing memories, ensuring it's a list
    memories: list = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(memories, list):
        memories = []

    now = datetime.now(timezone.utc).isoformat()

    # Build the entry from either a dict or a string
    if isinstance(new, dict):
        entry: dict = new.copy()
        entry.setdefault("id", str(uuid.uuid4()))
        entry.setdefault("timestamp", now)
        entry.setdefault("emotion", emotion or detect_emotion(entry.get("content", "")))
        entry.setdefault("event_type", event_type)
        entry.setdefault("agent", agent)
        entry.setdefault("importance", importance)
        entry.setdefault("priority", priority)
        entry.setdefault("referenced", referenced)
        entry.setdefault("pin", pin)
        entry.setdefault("related_memory_ids", related_memory_ids or [])
        entry.setdefault("recall_count", recall_count)
        entry.setdefault("context", context)
    elif isinstance(new, str):
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": now,
            "content": new.strip(),
            "emotion": emotion or detect_emotion(new),
            "event_type": event_type,
            "agent": agent,
            "importance": importance,
            "priority": priority,
            "referenced": referenced,
            "pin": pin,
            "related_memory_ids": related_memory_ids or [],
            "recall_count": recall_count,
            "context": context,
        }
    else:
        log_error("update_long_memory: Invalid 'new' argument.")
        return

    # Generate or attach embedding
    try:
        emb = embedding if embedding is not None else get_embedding(entry.get("content", ""))
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
        entry["embedding"] = emb
    except Exception as exc:
        log_error(f"update_long_memory: Embedding failed: {exc}")
        entry["embedding"] = []

    # Check for duplicates in the most recent window
    for m in memories[-DUPLICATE_WINDOW:]:
        if m.get("content", "") == entry.get("content", "") and m.get("event_type", "") == entry.get("event_type", ""):
            log_private(f"[long_memory] Skipped duplicate memory: {entry['content'][:50]}")
            return

    # Append the new entry
    memories.append(entry)

    # Optionally trigger a reward signal for important/priority memories
    if context is not None and (importance >= 2 or priority >= 2 or referenced >= 3):
        try:
            from emotion.reward_signals.reward_signals import release_reward_signal
            intensity = min(1.0, importance * 0.5 + priority * 0.5 + 0.1 * referenced)
            release_reward_signal(
                context=context,
                signal_type="dopamine",
                actual_reward=intensity,
                expected_reward=0.5,
                effort=0.4,
                mode="phasic",
                source="memory_update",
            )
        except Exception as exc:
            log_error(f"update_long_memory: reward signalling failed: {exc}")

    # Prune if the memory exceeds the maximum size
    if len(memories) > MAX_LONG_MEMORY:
        prune_long_memory(max_total=MAX_LONG_MEMORY)
        memories = load_json(LONG_MEMORY_FILE, default_type=list)

    save_json(LONG_MEMORY_FILE, memories)


def reevaluate_memory_significance() -> None:
    """Recompute the 'effectiveness_score' of all entries in long-term memory."""
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        return

    for mem in long_memory:
        if not isinstance(mem, dict):
            continue

        content = mem.get("content", "").lower()
        emotion = mem.get("emotion", "neutral")
        score = mem.get("effectiveness_score", 5)

        # Reward memories tagged as lessons or containing strong emotions
        if "lesson:" in content:
            score = min(score + 1, 10)
        if emotion in {"grief", "joy", "fear", "pride"}:
            score = min(score + 1, 10)

        # Adjust based on recall_count
        recall_count = mem.get("recall_count", 0)
        if recall_count >= 5:
            score = min(score + 2, 10)
        elif recall_count >= 2:
            score = min(score + 1, 10)

        # Pins have a minimum significance
        if mem.get("pin", False):
            score = max(score, 8)

        # Age penalty
        try:
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(mem["timestamp"])).days
            if age_days > 30 and score > 3 and not mem.get("pin", False):
                score -= 1
        except Exception:
            pass

        # Related memories bonus
        if isinstance(mem.get("related_memory_ids"), list) and len(mem["related_memory_ids"]) > 2:
            score = min(score + 1, 10)

        mem["effectiveness_score"] = score

    save_json(LONG_MEMORY_FILE, long_memory)


def prune_long_memory(max_total: int = MAX_LONG_MEMORY) -> None:
    """Reduce long-term memory to `max_total` items by removing low scoring entries and summarising them."""
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(long_memory, list):
        return

    if len(long_memory) <= max_total:
        return

    def memory_score(mem: dict) -> int:
        try:
            score = 0
            emotion = mem.get("emotion", "")
            content = mem.get("content", "").lower()

            if emotion in STRONG_EMOTIONS:
                score += 3
            if "lesson:" in content:
                score += 4
            score += mem.get("effectiveness_score", 5) // 2

            # Recency boost and age penalty
            delta = datetime.now(timezone.utc) - datetime.fromisoformat(mem.get("timestamp", ""))
            days_old = delta.days
            if days_old < 3:
                score += 3
            elif days_old < 7:
                score += 1
            elif days_old > 30:
                score -= 2

            # Pin multiplier
            if mem.get("pin", False):
                score += 10000

            # Recall bonus
            rc = mem.get("recall_count", 0)
            if rc >= 5:
                score += 2
            elif rc >= 2:
                score += 1

            # Related memory bonus
            if isinstance(mem.get("related_memory_ids"), list) and len(mem["related_memory_ids"]) > 2:
                score += 1

            score += int(mem.get("importance", 1))
            score += int(mem.get("priority", 1))

        except Exception as exc:
            log_error(f"prune_long_memory: scoring failed: {exc}")
            score = 0
        return score

    # Sort memories by their score and timestamp
    scored = sorted(long_memory, key=lambda m: (memory_score(m), m.get("timestamp", "")), reverse=True)
    pins = [m for m in scored if m.get("pin", False)]
    non_pins = [m for m in scored if not m.get("pin", False)]

    kept = pins + non_pins[: max_total - len(pins)]
    removed = non_pins[max_total - len(pins) :]

    if removed:
        summary = summarize_memories(removed)
        if summary:
            merged = {
                "content": f"🧠 Summary of faded memories:\n{summary}",
                "emotion": detect_emotion(summary),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            kept.append(merged)
        update_values_with_lessons()

    save_json(LONG_MEMORY_FILE, kept)

    # Log pruning to private thoughts file
    try:
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(
                f"\n[{datetime.now(timezone.utc)}] Orrin pruned {len(removed)} long memories. "
                f"{'Summarized and merged.' if removed else ''}\n"
            )
    except Exception as exc:
        log_error(f"prune_long_memory: failed writing to private thoughts: {exc}")


def remember(
    event: Any,
    context: Optional[dict] = None,
    emotion: Optional[str] = None,
    event_type: str = "event",
    agent: str = "orrin",
    importance: int = 1,
    priority: int = 1,
    referenced: int = 0,
    pin: bool = False,
    related_memory_ids: Optional[List[str]] = None,
) -> None:
    """Store an event in long-term memory with deduplication and embeddings."""
    long_memory: list = load_json(LONG_MEMORY_FILE, default_type=list)
    now = datetime.now(timezone.utc).isoformat()
    content_str = event.strip() if isinstance(event, str) else str(event)

    # Skip duplicates within the recent window
    for m in long_memory[-DUPLICATE_WINDOW:]:
        if m.get("content", "") == content_str and m.get("event_type", "") == event_type:
            log_private(f"[long_memory] Skipped duplicate memory: {content_str[:50]}")
            return

    try:
        emb = get_embedding(content_str)
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
    except Exception as exc:
        log_error(f"remember: embedding failed: {exc}")
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
        "context": context,
    }

    long_memory.append(entry)
    save_json(LONG_MEMORY_FILE, long_memory)