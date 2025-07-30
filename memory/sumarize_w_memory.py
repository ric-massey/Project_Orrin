from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.memory_utils import summarize_memories
from emotion.emotion import detect_emotion
from memory.long_memory import update_long_memory
from utils.embedder import get_embedding
from utils.log import log_private


def summarize_and_promote_working_memory(memories: List[Dict[str, Any]]) -> None:
    """
    Summarize a batch of working-memory entries and promote the result to long-term memory.

    The summary includes aggregated metadata (e.g. total references, whether any entry was pinned,
    the set of event types) and an embedding generated from the summary content. Once
    constructed, the summary is passed to `update_long_memory()` and a log entry is made.

    Args:
        memories: A list of working-memory entries (dictionaries). If empty, no action is taken.
    """
    if not memories:
        return

    # Collect metadata
    referenced = [m for m in memories if m.get("referenced", 0) > 0]
    pins = [m for m in memories if m.get("pin", False)]
    topics = {m.get("event_type", "thought") for m in memories}

    summary_text = summarize_memories(memories)
    extra_info = ""
    if referenced:
        extra_info += f"\nReferenced {len(referenced)} times during reasoning."
    if pins:
        extra_info += f"\nPinned items: {[m.get('content', '')[:40] for m in pins]}"
    if topics:
        extra_info += f"\nEvent types: {', '.join(topics)}"

    related_ids = [m.get("id") for m in memories if m.get("id")]
    referenced_total = sum(m.get("referenced", 0) for m in memories)
    pin_flag = any(m.get("pin", False) for m in memories)
    decay_avg = sum(m.get("decay", 1.0) for m in memories) / max(len(memories), 1)
    recall_total = sum(m.get("recall_count", 0) for m in memories)

    content_str = f"📝 Working memory summary: {summary_text}{extra_info}"

    # Ensure embedding is a simple list
    embedding = get_embedding(content_str)
    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()

    summary_entry = {
        "content": content_str,
        "emotion": detect_emotion(summary_text),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "summary",
        "agent": "orrin",
        "importance": 2,
        "priority": 2,
        "referenced": referenced_total,
        "pin": pin_flag,
        "decay": decay_avg,
        "recall_count": recall_total,
        "related_memory_ids": related_ids,
        "embedding": embedding,
    }

    update_long_memory(summary_entry)
    log_private("[working_memory] New working memory summary promoted to long-term.")