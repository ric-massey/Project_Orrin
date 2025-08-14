from __future__ import annotations

from typing import Any, Dict, Iterable
from datetime import datetime, timezone
from paths import STATE_SNAPSHOT_FILE
from utils.json_utils import load_json, save_json

# Keys that can get huge; omit or truncate
_DEFAULT_EXCLUDES: set[str] = {
    "long_memory", "working_memory", "raw_signals", "top_signals", "available_functions"
}

def _json_safe(obj: Any) -> Any:
    """Best-effort conversion to JSON-safe types."""
    try:
        # Fast path: already serializable
        save_json("/dev/null", obj)  # will raise on non-serializable
        return obj
    except Exception:
        pass
    # Fallbacks
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "tolist"):  # numpy arrays, etc.
        try:
            return obj.tolist()
        except Exception:
            return repr(obj)
    # Last resort: repr
    return repr(obj)

def _filtered_context(ctx: Dict[str, Any], exclude: Iterable[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (ctx or {}).items():
        if k in exclude:
            continue
        # Trim very large lists
        if isinstance(v, list) and len(v) > 200:
            out[k] = _json_safe(v[-200:])  # keep tail
        else:
            out[k] = _json_safe(v)
    return out

def save_snapshot(context: Dict[str, Any], result: Dict[str, Any], *, exclude: Iterable[str] = _DEFAULT_EXCLUDES) -> None:
    snap = {
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": _filtered_context(context or {}, exclude),
        "result": _json_safe(result or {}),
    }
    save_json(STATE_SNAPSHOT_FILE, snap)

def load_snapshot() -> Dict[str, Any]:
    data = load_json(STATE_SNAPSHOT_FILE, default_type=dict)
    return data if isinstance(data, dict) else {}

def has_unfinished(snapshot: Dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict):
        return False
    ctx = snapshot.get("context") or {}
    pending = ctx.get("pending_actions", [])
    if isinstance(pending, (list, tuple)):
        return len(pending) > 0
    # If a single action accidentally stored as dict/str, still treat as unfinished
    return bool(pending)