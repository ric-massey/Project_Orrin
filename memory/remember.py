from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, List
import uuid

from emotion.emotion import detect_emotion
from paths import LONG_MEMORY_FILE
from utils.embedder import get_embedding
from utils.json_utils import load_json, save_json
from utils.log import log_error, log_private
from memory.long_memory import DUPLICATE_WINDOW

def _emotion_name(e: Any) -> str:
    """Coerce detect_emotion output into a lowercase string."""
    if isinstance(e, dict):
        return str(e.get("emotion", "neutral")).lower()
    return str(e or "neutral").lower()

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
    if not isinstance(long_memory, list):
        long_memory = []

    now = datetime.now(timezone.utc).isoformat()

    # Normalize content to a string but keep raw if non-string
    raw: Any = None
    if isinstance(event, str):
        content_str = event.strip()
    else:
        raw = event
        content_str = str(event).strip()

    if not content_str:
        # Nothing meaningful to store
        return

    # Deduplication (compare using string form)
    for m in long_memory[-DUPLICATE_WINDOW:]:
        m_content = m.get("content", "")
        m_content_str = str(m_content) if not isinstance(m_content, str) else m_content
        if m_content_str == content_str and m.get("event_type", "") == event_type:
            log_private(f"[long_memory] Skipped duplicate memory: {content_str[:50]}")
            return

    # Get embedding (always use string content)
    try:
        emb = get_embedding(content_str)
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
    except Exception as exc:
        log_error(f"remember: embedding failed: {exc}")
        emb = []

    detected = _emotion_name(emotion or detect_emotion(content_str))

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "content": content_str,              # normalized string content
        "raw": raw,                          # optional original object
        "emotion": detected,
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