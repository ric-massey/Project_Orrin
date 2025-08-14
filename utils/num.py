# utils/num.py
from __future__ import annotations
from typing import Any

def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        # if it's a dict-like, try summing numeric values
        try:
            return sum(float(v) for v in x.values())  # type: ignore[attr-defined]
        except Exception:
            return default

def safe_neg(x: Any) -> float:
    return -safe_float(x, 0.0)
