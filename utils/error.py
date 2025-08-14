# utils/errors.py
from __future__ import annotations
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from utils.log import log_error, log_model_issue

# Prefer your project paths; fall back sanely if missing
try:
    from paths import INCIDENTS_FILE  # e.g., DATA_DIR / "incidents.jsonl"
except Exception:
    from pathlib import Path
    try:
        from paths import DATA_DIR  # if available
        INCIDENTS_FILE = (DATA_DIR / "incidents.jsonl")  # type: ignore
    except Exception:
        INCIDENTS_FILE = Path("data") / "incidents.jsonl"  # type: ignore

# JSONL appender (use your helper if present; else local fallback)
try:
    from utils.json_utils import append_jsonl  # preferred helper
except Exception:
    import json, os, tempfile
    from pathlib import Path

    def append_jsonl(path: str | "Path", obj: Any) -> None:  # type: ignore
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        # simple, safe append
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(p.parent), encoding="utf-8") as tmp:
            tmp.write(line)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        with open(p, "a", encoding="utf-8") as out, open(tmp_name, "r", encoding="utf-8") as src:
            out.write(src.read())
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(x: Any, limit: int = 20000) -> str:
    try:
        s = str(x)
    except Exception:
        s = repr(x)
    # keep lines controllable in JSONL
    return s[:limit]


def build_error_event(
    exc: BaseException,
    *,
    phase: str,  # "think" | "action" | "cognition" | "tool" | "loop" | etc.
    context: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a rich, serializable error event Orrin can learn from.
    """
    ctx = context or {}
    try:
        trace = traceback.format_exc()
    except Exception:
        trace = ""

    # keep context lightweight to avoid dumping secrets / huge blobs
    ctx_keys = sorted(list(ctx.keys()))[:50]
    ctx_focus = {
        k: ctx.get(k)
        for k in ["mode", "attention_mode", "focus_goal", "committed_goal", "action_debt", "last_action_ts"]
        if k in ctx
    }

    ev: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "ts": _utc_now(),
        "phase": str(phase),
        "type": exc.__class__.__name__,
        "msg": _safe_str(exc, limit=2000),
        "trace": _safe_str(trace, limit=20000),
        "context_keys": ctx_keys,
        "context_focus": ctx_focus,
        "extra": extra or {},
    }
    return ev


def record_error(ev: Dict[str, Any]) -> None:
    """
    Persist an error event to incidents.jsonl and log a concise, operator-friendly line.
    """
    try:
        append_jsonl(INCIDENTS_FILE, ev)
    except Exception as e:
        # never crash on logging; at least surface a model issue
        log_model_issue(f"[record_error] append failed: {e}")

    # brief console/operator line
    try:
        phase = ev.get("phase", "?")
        etype = ev.get("type", "Exception")
        msg = ev.get("msg", "")[:300]
        log_error(f"[{phase}] {etype}: {msg}")
    except Exception:
        # swallow final logging failures silently
        pass


def record_exception(
    exc: BaseException,
    *,
    phase: str,
    context: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience: build + record in one call. Returns the event dict for further use.
    """
    ev = build_error_event(exc, phase=phase, context=context, extra=extra)
    record_error(ev)
    return ev
