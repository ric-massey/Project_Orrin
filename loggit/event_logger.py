# event_logger.py — Central JSONL event logger with canonical types.

import json
import time
from enum import Enum
from pathlib import Path

from paths import EVENTS_FILE 

EVENTS_PATH = Path(EVENTS_FILE)
EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

class EventKind(str, Enum):
    DECISION = "DECISION"
    ACTION_START = "ACTION_START"
    ACTION_END = "ACTION_END"
    REWARD_APPLIED = "REWARD_APPLIED"
    ERROR = "ERROR"
    EVAL = "EVAL"

def log_event(kind: EventKind | str, **payload) -> dict:
    """
    Append a single event record to the JSONL stream.
    - kind: EventKind (or str)
    - payload: any JSON-serializable fields
    """
    # allow plain strings too
    kind_str = kind.value if isinstance(kind, EventKind) else str(kind)

    rec = {
        "ts": time.time(),                 # unix timestamp
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": kind_str,
        **payload,
    }

    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return rec