# registry/behavior_registry.py
from __future__ import annotations
import inspect
from typing import Dict, Callable, List, Tuple
from registry.utils import iter_modules, safe_import, extract_callables
from paths import BEHAVIORAL_FUNCTIONS_LIST_FILE
from utils.json_utils import save_json
from utils.log import log_error, log_activity

_ALLOWED_PREFIXES: Tuple[str, ...] = ("act_", "tool_", "execute_", "say_", "report_", "sandbox_", "call_")

def _is_action(fn: Callable) -> bool:
    # Prefer a manifest flag if you use your @manifest decorator elsewhere
    mf = getattr(fn, "__manifest__", None)
    if mf and hasattr(mf, "is_action"):
        try:
            return bool(mf.is_action)
        except Exception:
            pass
    # Fallback: treat discovered behavior callables as actions by default
    return True

def discover_behavioral_functions() -> Dict[str, Dict[str, object]]:
    """
    Returns a mapping:
      name -> {"function": callable, "is_action": bool}

    Scans ALL modules under the 'behavior' package (including subfolders).
    First collects functions matched by _ALLOWED_PREFIXES via extract_callables(...),
    then adds ANY other *public* functions defined in the module (keep-first).
    Private helpers (names starting with '_') are excluded.
    """
    funcs: Dict[str, Dict[str, object]] = {}
    for mod_name in iter_modules("behavior"):
        mod = safe_import(mod_name)
        if not mod:
            continue

        # 1) Prefix-based discovery
        try:
            raw_found = extract_callables(mod, _ALLOWED_PREFIXES)  # {name: callable}
        except Exception:
            raw_found = {}

        for name, fn in raw_found.items():
            if not isinstance(name, str) or name.startswith("_"):
                continue  # skip private helpers
            if name in funcs:
                try:
                    log_error(f"[behavior discover] Duplicate function name '{name}' from {mod_name} ignored (keeping first).")
                except Exception:
                    pass
                continue
            funcs[name] = {"function": fn, "is_action": _is_action(fn)}

        # 2) Add other public functions defined in this module (exclude re-exported/imported & private)
        try:
            for name, fn in inspect.getmembers(mod, inspect.isfunction):
                if getattr(fn, "__module__", None) != getattr(mod, "__name__", None):
                    continue  # only functions defined in this module
                if not isinstance(name, str) or name.startswith("_"):
                    continue  # skip private helpers
                if name in funcs:
                    continue  # keep-first
                funcs[name] = {"function": fn, "is_action": _is_action(fn)}
        except Exception:
            # best-effort; don't fail discovery because of one bad module
            pass

    return funcs

def persist_names(funcs: Dict[str, Dict[str, object]]) -> List[str]:
    # Persist only public names (no leading underscore)
    names = sorted(n for n in funcs.keys() if isinstance(n, str) and not n.startswith("_"))
    try:
        # Write full catalog entries the LLM can read (name + definition),
        # while still returning just the names for callers.
        items: List[Dict[str, str]] = []
        for name in names:
            meta = funcs.get(name, {})
            fn = meta.get("function") if isinstance(meta, dict) else None
            definition = name  # fallback
            if callable(fn):
                try:
                    sig = str(inspect.signature(fn))
                except Exception:
                    sig = "()"
                doc = (fn.__doc__ or "").strip()
                definition = f"{name}{sig}\n{doc}" if doc else f"{name}{sig}"
            items.append({"name": name, "definition": definition})
        save_json(BEHAVIORAL_FUNCTIONS_LIST_FILE, items)
        try:
            log_activity(f"[behavior discover] Persisted {len(names)} behavioral function names + definitions.")
        except Exception:
            pass
    except Exception as e:
        try:
            log_error(f"[behavior discover] Failed to persist names/definitions: {e}")
        except Exception:
            pass
    return names


# Build cache at import (simple and fast for your layout)
BEHAVIORAL_FUNCTIONS: Dict[str, Dict[str, object]] = discover_behavioral_functions()
persist_names(BEHAVIORAL_FUNCTIONS)

def refresh() -> Dict[str, Dict[str, object]]:
    """Optional: call if you hot-reload behaviors at runtime."""
    global BEHAVIORAL_FUNCTIONS
    BEHAVIORAL_FUNCTIONS = discover_behavioral_functions()
    persist_names(BEHAVIORAL_FUNCTIONS)
    return BEHAVIORAL_FUNCTIONS

import traceback, sys
def discover() -> Dict[str, Dict[str, object]]:
    sys.stderr.write("[TRACE] behavior_registry.discover() called\n" + "".join(traceback.format_stack(limit=8)))
    return discover_behavioral_functions()
