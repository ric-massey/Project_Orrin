from __future__ import annotations

# --- standardized import for project paths ---
try:
    from paths import *  # makes path constants available module-wide
except Exception:
    import importlib, sys, os
    _base = os.path.abspath(os.path.dirname(__file__))
    for _ in range(8):
        candidate = os.path.join(_base, "paths.py")
        if os.path.exists(candidate):
            if _base not in sys.path:
                sys.path.insert(0, _base)
            break
        _base = os.path.dirname(_base)
    from paths import *
# --- end standardized import ---

from dataclasses import dataclass, asdict, fields
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")

@dataclass
class FunctionManifest:
    name: str
    pre: Optional[List[str]] = None
    post: Optional[List[str]] = None
    cost: Optional[float] = None
    risk: Optional[float] = None
    latency: Optional[float] = None
    success_signal: Optional[str] = None
    is_action: bool = False

def _normalize_seq(val: Any) -> Optional[List[str]]:
    if val is None:
        return None
    if isinstance(val, str):
        return [val]
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val]
    return [str(val)]

def manifest(**meta: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    # Filter unknown keys to avoid TypeError when constructing the dataclass
    valid_keys = {f.name for f in fields(FunctionManifest)}
    clean_meta: Dict[str, Any] = {k: v for k, v in meta.items() if k in valid_keys}

    # Normalize pre/post if provided as scalars
    if "pre" in clean_meta:
        clean_meta["pre"] = _normalize_seq(clean_meta["pre"])
    if "post" in clean_meta:
        clean_meta["post"] = _normalize_seq(clean_meta["post"])

    def deco(fn: Callable[P, R]) -> Callable[P, R]:
        mf = FunctionManifest(
            name=getattr(fn, "__name__", clean_meta.get("name", "unknown")),
            **{k: v for k, v in clean_meta.items() if k != "name"},
        )
        setattr(fn, "__manifest__", mf)

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return fn(*args, **kwargs)

        # Keep the manifest on the returned callable
        setattr(wrapper, "__manifest__", mf)
        return wrapper
    return deco

def get_manifest_dict(fn: Callable[..., Any]) -> Dict[str, Any]:
    mf: Optional[FunctionManifest] = getattr(fn, "__manifest__", None)
    if mf is None:
        return {"name": getattr(fn, "__name__", "unknown")}
    d = asdict(mf)
    if not d.get("name"):
        d["name"] = getattr(fn, "__name__", "unknown")
    return d