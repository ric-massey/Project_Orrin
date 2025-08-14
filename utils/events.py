from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Union
from paths import EVENTS_FILE as _EVENTS_FILE

# Event types
DECISION = "DECISION"
ACTION_START = "ACTION_START"
ACTION_END = "ACTION_END"
OVERRIDE_TRIGGERED = "OVERRIDE_TRIGGERED"
REWARD_APPLIED = "REWARD_APPLIED"
MEMORY_WRITE = "MEMORY_WRITE"
ERROR = "ERROR"

def _as_path(p: Union[str, Path]) -> Path:
    return p if isinstance(p, Path) else Path(p)

EVENTS_FILE: Path = _as_path(_EVENTS_FILE)

def emit_event(event_type: str, payload: Dict[str, Any] | None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": str(event_type),
        "payload": payload or {},
    }
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_FILE.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Optional: avoid raising during telemetry
        # from utils.log import log_error
        # log_error(f"emit_event failed: {e}")
        pass