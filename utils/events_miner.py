from __future__ import annotations

import json
import ast
from collections import deque
from pathlib import Path
from typing import List, Dict, Any
from paths import EVENTS_FILE  # may be Path or str

def _as_path(p) -> Path:
    return p if isinstance(p, Path) else Path(p)

def _parse_line(line: str) -> Dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    # Try JSON first
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # Fallback to Python literal (for legacy repr lines)
    try:
        obj = ast.literal_eval(line)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None

def last_n_events(n: int = 400) -> List[Dict[str, Any]]:
    out: deque[Dict[str, Any]] = deque(maxlen=max(1, n))
    try:
        path = _as_path(EVENTS_FILE)
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                obj = _parse_line(line)
                if obj is not None:
                    out.append(obj)
    except Exception:
        return []
    return list(out)

def summarize_outcomes(evts: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_pick: Dict[str, int] = {}
    accepted = 0
    total = 0
    for e in evts:
        if not isinstance(e, dict):
            continue
        total += 1
        payload = e.get("payload") or {}
        dec = payload.get("decision") or {}
        pick = dec.get("picked")
        if isinstance(pick, str) and pick:
            by_pick[pick] = by_pick.get(pick, 0) + 1
        rew = payload.get("reward") or {}
        if bool(rew.get("acceptance_passed")):
            accepted += 1
    top = sorted(by_pick.items(), key=lambda x: (-x[1], x[0]))[:5]
    return {"accepted": accepted, "total": total, "top": top}