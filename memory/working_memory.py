from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
import uuid
import numpy as np

from emotion.emotion import detect_emotion
from utils.embedder import get_embedding
from utils.json_utils import load_json, save_json
from utils.log import log_private, log_error
from memory.summarize_w_memory import summarize_and_promote_working_memory
from paths import WORKING_MEMORY_FILE

MAX_WORKING_LOGS: int = 50  # adjust as needed

def _emotion_name(e: Any) -> str:
    if isinstance(e, dict):
        return str(e.get("emotion", "neutral")).lower()
    return str(e or "neutral").lower()

def _safe_embedding(text: str) -> list:
    try:
        emb = get_embedding(text)
        if isinstance(emb, np.ndarray):
            return emb.tolist()
        if isinstance(emb, list) and emb and isinstance(emb[0], np.ndarray):
            return emb[0].tolist()
        return emb or []
    except Exception as exc:
        log_error(f"update_working_memory: embedding failed: {exc}")
        return []

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
        entry.setdefault("content", entry.get("content", ""))  # ensure exists
        entry.setdefault("emotion", emotion or _emotion_name(detect_emotion(entry.get("content", ""))))
        entry.setdefault("event_type", event_type)
        entry.setdefault("agent", agent)
        entry.setdefault("importance", importance)
        entry.setdefault("priority", priority)
        entry.setdefault("referenced", int(referenced))
        entry.setdefault("recall_count", 0)
        entry.setdefault("pin", pin)
        entry.setdefault("decay", 1.0)
        entry.setdefault("related_memory_ids", related_memory_ids or [])
        emb = entry.get("embedding")
        if not emb:
            emb = _safe_embedding(entry.get("content", ""))
        elif isinstance(emb, np.ndarray):
            emb = emb.tolist()
        elif isinstance(emb, list) and emb and isinstance(emb[0], np.ndarray):
            emb = emb[0].tolist()
        entry["embedding"] = emb
    elif isinstance(new, str):
        content = new.strip()
        entry = {
            "id": str(uuid.uuid4()),
            "content": content,
            "emotion": emotion or _emotion_name(detect_emotion(content)),
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
            "embedding": _safe_embedding(content),
        }
    else:
        # Unsupported type, nothing to do
        return

    # Update decay and reference counts on existing memories
    for m in memories:
        if not m.get("pin"):
            m["decay"] = max(0.0, (m.get("decay", 1.0) or 1.0) - 0.02)
        if m.get("content") == entry.get("content"):
            m["referenced"] = m.get("referenced", 0) + entry.get("referenced", 0)
            m["decay"] = min(1.0, (m.get("decay", 1.0) or 1.0) + 0.1)

    # De-duplicate pinned entries by content
    if entry.get("pin"):
        memories = [m for m in memories if not (m.get("pin") and m.get("content") == entry.get("content"))]

    memories.append(entry)

    # Sort by pin, then priority/importance/decay, then timestamp (newest last)
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

    # Handle overflow: keep all pins, trim non-pins; never slice with a negative start
    if len(memories) > MAX_WORKING_LOGS:
        pins = [m for m in memories if m.get("pin")]
        non_pins = [m for m in memories if not m.get("pin")]

        capacity_for_non_pins = max(0, MAX_WORKING_LOGS - len(pins))
        dropped = non_pins[capacity_for_non_pins:]
        kept_non_pins = non_pins[:capacity_for_non_pins]

        # If pins alone exceed the cap, we keep them all (pins are never pruned)
        kept = pins + kept_non_pins

        if dropped:
            summarize_and_promote_working_memory(dropped)
            log_private(f"[working_memory] Promoted {len(dropped)} old entries to long-term memory summary.")

        memories = kept

    # Sort chronologically for the final write
    memories.sort(key=lambda m: m.get("timestamp", ""))
    save_json(WORKING_MEMORY_FILE, memories)