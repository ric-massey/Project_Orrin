from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import uuid
import numpy as np

from emotion.emotion import detect_emotion
from utils.embedder import get_embedding
from utils.json_utils import load_json, save_json
from utils.log import log_private
from memory.sumarize_w_memory import summarize_and_promote_working_memory
from paths import WORKING_MEMORY_FILE

MAX_WORKING_LOGS: int = 50  # adjust as needed

def update_working_memory(
    new: Any,
    emotion: Optional[str] = None,
    event_type: str = "thought",
    agent: str = "orrin",
    importance: int = 1,
    priority: int = 1,
    referenced: bool = False,
    pin: bool = False,
    related_memory_ids: Optional[List[str]] = None,
) -> None:
    """
    Add a new entry to working memory and manage pruning.

    Args:
        new: Either a string (the content of the thought) or a dict containing the entry fields.
        emotion: Optional override of the detected emotion.
        event_type: Category of the thought.
        agent: Identifier of the agent that produced the thought.
        importance: Subjective importance level.
        priority: Priority for retrieval.
        referenced: Flag indicating whether this thought references an existing long-term memory.
        pin: If True, prevents the entry from being pruned.
        related_memory_ids: List of IDs of related memories.

    Errors are logged via the project’s logging utilities; this function does not raise.
    """
    memories: list = load_json(WORKING_MEMORY_FILE, default_type=list)
    if not isinstance(memories, list):
        memories = []

    now = datetime.now(timezone.utc).isoformat()

    # Build or copy the entry
    if isinstance(new, dict):
        entry: dict = new.copy()
        entry.setdefault("id", str(uuid.uuid4()))
        entry.setdefault("timestamp", now)
        entry.setdefault("emotion", emotion or detect_emotion(entry.get("content", "")))
        entry.setdefault("event_type", event_type)
        entry.setdefault("agent", agent)
        entry.setdefault("importance", importance)
        entry.setdefault("priority", priority)
        entry.setdefault("referenced", int(referenced))
        entry.setdefault("recall_count", 0)
        entry.setdefault("pin", pin)
        entry.setdefault("decay", 1.0)
        entry.setdefault("related_memory_ids", related_memory_ids or [])
        # Normalise embedding to a plain list
        emb = entry.get("embedding") or get_embedding(entry.get("content", ""))
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()
        elif isinstance(emb, list) and emb and isinstance(emb[0], np.ndarray):
            emb = emb[0].tolist()
        entry["embedding"] = emb
    elif isinstance(new, str):
        emb = get_embedding(new)
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()
        elif isinstance(emb, list) and emb and isinstance(emb[0], np.ndarray):
            emb = emb[0].tolist()
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
            "recall_count": 0,
            "pin": pin,
            "decay": 1.0,
            "related_memory_ids": related_memory_ids or [],
            "embedding": emb,
        }
    else:
        return  # Unsupported type, nothing to do

    # Update decay and reference counts on existing memories
    for m in memories:
        if not m.get("pin"):
            m["decay"] = max(0.0, m.get("decay", 1.0) - 0.02)
        if m.get("content") == entry.get("content"):
            m["referenced"] = m.get("referenced", 0) + entry.get("referenced", 0)
            m["decay"] = min(1.0, m.get("decay", 1.0) + 0.1)

    # Remove any existing pinned entry with the same content
    if entry.get("pin"):
        memories = [m for m in memories if not (m.get("pin") and m.get("content") == entry.get("content"))]

    memories.append(entry)

    # Sort by pin, then priority/importance/decay, newest entries last
    memories.sort(
        key=lambda m: (
            m.get("pin", False),
            m.get("priority", 1),
            m.get("importance", 1),
            m.get("decay", 1.0),
            m.get("timestamp", ""),
        ),
        reverse=True,
    )

    # Handle overflow: promote dropped non-pin entries to long-term memory
    if len(memories) > MAX_WORKING_LOGS:
        pins = [m for m in memories if m.get("pin")]
        non_pins = [m for m in memories if not m.get("pin")]
        dropped = non_pins[MAX_WORKING_LOGS - len(pins) :]
        kept = non_pins[: MAX_WORKING_LOGS - len(pins)] + pins
        if dropped:
            summarize_and_promote_working_memory(dropped)
            log_private(f"[working_memory] Promoted {len(dropped)} old entries to long-term memory summary.")
        memories = kept

    # Sort chronologically for the final write
    memories.sort(key=lambda m: m.get("timestamp", ""))
    save_json(WORKING_MEMORY_FILE, memories)