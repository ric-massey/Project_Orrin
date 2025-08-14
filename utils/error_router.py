from __future__ import annotations
from typing import Any, Dict, Optional, Callable
from functools import wraps
import traceback
import inspect
import json as _json

from utils.log import log_error, log_model_issue
from utils.error import build_error_event, record_error  # from the self-heal plumbing
from utils.json_utils import append_jsonl
from paths import MODEL_FAILURES_FILE


def _to_model_failures(ev: Dict[str, Any]) -> None:
    try:
        append_jsonl(MODEL_FAILURES_FILE, ev)
    except Exception:
        # never let error logging crash the process
        pass


def route_exception(
    e: BaseException,
    *,
    phase: str,                       # "think" | "action" | "cognition" | "tool" | "loop"
    context: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    return_fn: Optional[Callable[[BaseException], Any]] = None,
) -> Any:
    """Route exception to the proper channel(s) and optionally return a structured value.
       Robust to callers passing tuples/None for context/extra. Includes a tuple/.get probe.
    """
    # ✅ Normalize first so downstream `.get` calls are always safe
    context = context if isinstance(context, dict) else {}
    extra = extra if isinstance(extra, dict) else {}

    et = e.__class__.__name__.lower()
    msg = str(e).lower()

    # 🔎 Probe: if we hit the classic "'tuple' object has no attribute 'get'" error,
    # dump the last frame, code line, local var types, and stack for pinpointing.
    if isinstance(e, AttributeError) and "'get'" in str(e):
        frames = list(inspect.getinnerframes(e.__traceback__, context=1))
        last = frames[-1] if frames else None
        debug = {}
        if last:
            try:
                local_types = {k: type(v).__name__ for k, v in list(last.frame.f_locals.items())[:50]}
            except Exception:
                local_types = {}
            debug = {
                "last_file": last.filename,
                "last_line": last.lineno,
                "last_func": last.function,
                "code": (last.code_context[0].strip() if last.code_context else ""),
                "locals": local_types,
                "stack": traceback.format_exc(),
            }
            # Single compact line you can copy/paste
            try:
                log_error(f"[{phase}] TUPLE-GET PROBE → {_json.dumps(debug, default=str)[:8000]}")
            except Exception:
                # Never let the probe itself crash routing
                pass

    # Build one rich event for learning/self-heal
    ev = build_error_event(e, phase=phase, context=context, extra=extra)

    # Heuristics for model-layer issues
    is_model = any([
        "openai" in et or "openai" in msg,
        "jsondecodeerror" in et,
        "token" in msg or "max context" in msg,
        "rate limit" in msg or "429" in msg,
        "invalid_request_error" in et or "badrequest" in msg,
    ])

    if is_model:
        log_model_issue(f"[{phase}] {e.__class__.__name__}: {e}")
        _to_model_failures(ev)        # separate JSONL stream for model failures
        return return_fn(e) if return_fn else None

    # Transient IO-ish problems can be “issues” (not fatal)
    is_transient = any([
        "timeout" in msg, "timed out" in msg, "connection" in msg, "reset" in msg,
    ])
    if is_transient:
        log_model_issue(f"[{phase}] transient: {e}")
        record_error(ev)              # keep in incidents for learning
        return return_fn(e) if return_fn else None

    # Default: real runtime bug → loud error + incident
    log_error(f"[{phase}] {e.__class__.__name__}: {e}")
    record_error(ev)

    # If the caller supplied a return mapper, use it; else re-raise so callers see the failure
    if return_fn:
        return return_fn(e)
    raise


def catch_and_route(phase: str, *, return_on_error: Optional[Callable[[BaseException], Any]] = None):
    """
    Wrap a function so any exception gets routed to the right logs + incidents.
    If return_on_error is provided, exceptions won't be raised; that value is returned instead.
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Pass through whatever the caller labeled as 'context';
            # route_exception will normalize it to a dict.
            ctx = kwargs.get("context")
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                return route_exception(e, phase=phase, context=ctx, return_fn=return_on_error)
        return wrapper
    return deco
