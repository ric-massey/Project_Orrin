from __future__ import annotations

import importlib
import pkgutil
import inspect
from types import ModuleType
from typing import Dict, Callable, Iterable, Optional

def iter_modules(package_name: str) -> Iterable[str]:
    """Yield fully-qualified module names under a package (skips private segments)."""
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        # Not a package (single module) — nothing to walk
        return iter(())
    for m in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        # Skip any module path containing private segments like foo._bar.baz
        if any(seg.startswith("_") for seg in m.name.split(".")):
            continue
        yield m.name

def safe_import(module_name: str) -> Optional[ModuleType]:
    """Import a module, returning None on failure (quietly)."""
    try:
        return importlib.import_module(module_name)
    except Exception:
        # You could log here if desired
        return None

def extract_callables(
    mod: ModuleType,
    allowed_prefixes: Optional[Iterable[str]] = None
) -> Dict[str, Callable]:
    """
    Return top-level functions in `mod` (optionally filtered by name prefixes).
    Skips private names and re-exported functions from other modules.
    """
    out: Dict[str, Callable] = {}
    # isfunction -> only Python functions defined at module level
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        if obj.__module__ != mod.__name__:
            # Skip re-exports (functions not defined in this module)
            continue
        if allowed_prefixes and not any(name.startswith(p) for p in allowed_prefixes):
            continue
        out[name] = obj
    return out