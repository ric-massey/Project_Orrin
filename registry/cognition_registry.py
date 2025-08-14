# registry/cognition_registry.py
from __future__ import annotations
import inspect

from typing import Dict, Callable, List, Tuple
from registry.utils import iter_modules, safe_import, extract_callables
from paths import COGNITIVE_FUNCTIONS_LIST_FILE
from utils.json_utils import save_json
from utils.log import log_error, log_activity

# Narrow, intentional entry-point prefixes for cognition functions
_ALLOWED_PREFIXES: Tuple[str, ...] = (
    "reflect_",
    "plan_",
    "summarize_",
    "repair_",
    "analyze_",
    "decide_",
    "dream_",
    "introspect_",
)

def _is_cognition(fn: Callable) -> bool:
    """
    Prefer an explicit manifest flag if you use one (e.g., via a decorator).
    Defaults to True to keep things simple/forgiving.
    """
    mf = getattr(fn, "__manifest__", None)
    if mf and hasattr(mf, "is_cognition"):
        try:
            return bool(mf.is_cognition)
        except Exception:
            pass
    return True

def _merge_custom(funcs: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    """
    Optionally merge user-defined cognition from core.manager.load_custom_cognition().
    Accepts either {name: callable} or {name: {"function": callable, ...}}.
    """
    try:
        from core.manager import load_custom_cognition  # type: ignore
    except Exception:
        return funcs

    try:
        custom = load_custom_cognition()
        if isinstance(custom, dict):
            for name, obj in custom.items():
                # Skip private helpers from custom too
                if isinstance(name, str) and name.startswith("_"):
                    continue
                if callable(obj):
                    funcs[name] = {"function": obj, "is_cognition": True}
                elif isinstance(obj, dict) and callable(obj.get("function")):
                    funcs[name] = {
                        "function": obj["function"],
                        "is_cognition": bool(obj.get("is_cognition", True)),
                    }
        return funcs
    except Exception as e:
        try:
            log_error(f"[cognition discover] Failed merging custom cognition: {e}")
        except Exception:
            pass
        return funcs

def discover_cognitive_functions() -> Dict[str, Dict[str, object]]:
    """
    Scan ALL cognition.* modules (including subpackages) and return:
        { name: { "function": callable, "is_cognition": bool } }

    First collects functions that match _ALLOWED_PREFIXES via extract_callables(...),
    then adds ANY other *public* functions defined in the module (keep-first on duplicates).
    Private helpers (names starting with '_') are excluded.
    """
    funcs: Dict[str, Dict[str, object]] = {}
    for mod_name in iter_modules("cognition"):
        mod = safe_import(mod_name)
        if not mod:
            continue

        # 1) Prefix-based discovery
        try:
            found = extract_callables(mod, _ALLOWED_PREFIXES)  # {name: callable}
        except Exception:
            found = {}

        for name, fn in found.items():
            if not isinstance(name, str) or name.startswith("_"):
                continue  # drop private helpers
            if name in funcs:
                try:
                    log_error(f"[cognition discover] Duplicate '{name}' from {mod_name} ignored (keeping first).")
                except Exception:
                    pass
                continue
            funcs[name] = {"function": fn, "is_cognition": _is_cognition(fn)}

        # 2) Include other public functions defined in this module (no underscores)
        try:
            for name, fn in inspect.getmembers(mod, inspect.isfunction):
                if getattr(fn, "__module__", None) != getattr(mod, "__name__", None):
                    continue  # only functions defined in this module
                if not isinstance(name, str) or name.startswith("_"):
                    continue  # skip private helpers
                if name in funcs:
                    continue  # keep-first
                funcs[name] = {"function": fn, "is_cognition": _is_cognition(fn)}
        except Exception:
            # best-effort; don't fail discovery because of one bad module
            pass

    # Merge any custom cognition last (also skips private)
    funcs = _merge_custom(funcs)
    return funcs

def persist_names(funcs: Dict[str, Dict[str, object]]) -> List[str]:
    """
    Write a list of {name, definition} so the LLM can read meanings.
    Still returns the plain list of names for code that uses it.
    Private helpers (names starting with '_') are filtered out here as well.
    """
    names = sorted(n for n in funcs.keys() if isinstance(n, str) and not n.startswith("_"))
    try:
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
        save_json(COGNITIVE_FUNCTIONS_LIST_FILE, items)
        try:
            log_activity(f"[cognition discover] Persisted {len(names)} cognitive function names + definitions.")
        except Exception:
            pass
    except Exception as e:
        try:
            log_error(f"[cognition discover] Failed to persist names/definitions: {e}")
        except Exception:
            pass
    return names

# -------- Global cache (mirrors behavior_registry) --------
COGNITIVE_FUNCTIONS: Dict[str, Dict[str, object]] = discover_cognitive_functions()
persist_names(COGNITIVE_FUNCTIONS)

def refresh() -> Dict[str, Dict[str, object]]:
    """
    Optional hot-reload entry point if you add/remove cognition at runtime.
    Re-discovers, persists names, and updates the global.
    """
    global COGNITIVE_FUNCTIONS
    COGNITIVE_FUNCTIONS = discover_cognitive_functions()
    persist_names(COGNITIVE_FUNCTIONS)
    return COGNITIVE_FUNCTIONS

# -------- Convenience accessors --------
def as_callables() -> Dict[str, Callable]:
    """
    Flatten to a simple {name: function} mapping.
    Useful for callers that prefer direct callables instead of metadata dicts.
    Private helpers (underscore names) are excluded for safety.
    """
    out: Dict[str, Callable] = {}
    for name, meta in COGNITIVE_FUNCTIONS.items():
        if not isinstance(name, str) or name.startswith("_"):
            continue
        fn = meta.get("function") if isinstance(meta, dict) else None
        if callable(fn):
            out[name] = fn
    return out

def discover() -> Dict[str, Callable]:
    """
    Compatibility helper to mirror newer 'registry.cognition_registry.discover()' usage
    found elsewhere in the codebase. Returns {name: callable}.
    """
    return as_callables()
