from utils.load_utils import load_json
from utils.json_utils import save_json
from datetime import datetime, timezone 
from utils.log import log_private
from memory.sumarize_w_memory import summarize_and_promote_working_memory

from paths import WORKING_MEMORY_FILE


MAX_WORKING_LOGS = 300

from datetime import datetime, timezone
from emotion.emotion import detect_emotion
from utils.json_utils import save_json, load_json
from utils.log import log_private
from utils.embedder import get_embedding  # <-- YOU NEED THIS: a function to get an embedding vector for text
import uuid
import numpy as np

MAX_WORKING_LOGS = 60  # adjust as needed
WORKING_MEMORY_FILE = "working_memory.json"


def update_working_memory(
    new,
    emotion=None,
    event_type="thought",
    agent="orrin",
    importance=1,
    priority=1,
    referenced=False,
    pin=False,
    related_memory_ids=None
):
    """
    Adds a new memory to working memory with human-like metadata for deep recall.
    """
    memories = load_json(WORKING_MEMORY_FILE, default_type=list)
    if not isinstance(memories, list):
        memories = []

    now = datetime.now(timezone.utc).isoformat()
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
        entry.setdefault("recall_count", 0)
        entry.setdefault("pin", pin)
        entry.setdefault("decay", 1.0)
        entry.setdefault("related_memory_ids", related_memory_ids or [])
        # ---- Embedding ----
        emb = get_embedding(entry.get("content", ""))
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
        return

    # ---- 2. Update Reference/Decay ----
    for m in memories:
        if not m.get("pin", False):
            m["decay"] = max(0.0, m.get("decay", 1.0) - 0.02)
        if m.get("content", "") == entry.get("content", ""):
            m["referenced"] = m.get("referenced", 0) + entry.get("referenced", 0)
            m["decay"] = min(1.0, m.get("decay", 1.0) + 0.1)

    # ---- 3. Append and Pin Deduplication ----
    if entry.get("pin", False):
        memories = [
            m for m in memories
            if not (m.get("pin", False) and m.get("content", "") == entry.get("content", ""))
        ]
    memories.append(entry)

    # ---- 4. Sorting: Pins First, Then Priority/Importance/Decay ----
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

    # ---- 5. Pruning (pins stay, others summarized/promoted to long-term) ----
    if len(memories) > MAX_WORKING_LOGS:
        pins = [m for m in memories if m.get("pin", False)]
        non_pins = [m for m in memories if not m.get("pin", False)]
        dropped = non_pins[MAX_WORKING_LOGS - len(pins):]
        kept = non_pins[:MAX_WORKING_LOGS - len(pins)] + pins

        if dropped:
            summarize_and_promote_working_memory(dropped)
            log_private(f"[working_memory] Promoted {len(dropped)} old entries to long-term memory summary.")

        memories = kept + pins

    # ---- 6. Final chronological sort ----
    memories = sorted(memories, key=lambda m: m.get("timestamp", ""))

    save_json(WORKING_MEMORY_FILE, memories)