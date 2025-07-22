
from datetime import datetime, timezone

def summarize_and_promote_working_memory(memories):
    from utils.memory_utils import summarize_memories
    from emotion.emotion import detect_emotion
    from memory.long_memory import update_long_memory
    from utils.log import log_private
    """
    Summarizes a list of working memory entries and promotes to long-term memory
    using the official update_long_memory() function.
    """
    if not memories:
        return
    referenced = [m for m in memories if m.get("referenced", 0) > 0]
    pins = [m for m in memories if m.get("pin", False)]
    topics = set(m.get("event_type", "thought") for m in memories)
    summary_text = summarize_memories(memories)
    extra = ""
    if referenced:
        extra += f"\nReferenced {len(referenced)} times during reasoning."
    if pins:
        extra += f"\nPinned items: {[m['content'][:40] for m in pins]}"
    if topics:
        extra += f"\nEvent types: {', '.join(topics)}"
    summary_entry = {
        "content": f"📝 Working memory summary: {summary_text}{extra}",
        "emotion": detect_emotion(summary_text),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "summary",
        "agent": "orrin",
        "importance": 2,
        "priority": 2,
    }
    # Only add if not a duplicate summary (prevents summary spam on rapid calls)
    # Rely on update_long_memory to do any needed duplicate checking/pruning
    update_long_memory(summary_entry)
    log_private("[working_memory] New working memory summary promoted to long-term.")