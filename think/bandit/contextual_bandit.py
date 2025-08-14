# Contextual epsilon-greedy bandit with linear features and persistence.
from __future__ import annotations

import random, math
from typing import Dict, List, Optional
from pathlib import Path

# Prefer paths.py definitions; fall back to data/bandit_state.json
try:
    from paths import BANDIT_STATE_FILE as _BANDIT_PATH  # preferred
except Exception:
    try:
        from paths import BANDIT_STATE_JSON as _BANDIT_PATH 
    except Exception:
        try:
            from paths import DATA_DIR as _DATA_DIR
            _BANDIT_PATH = _DATA_DIR / "bandit_state.json"
        except Exception:
            _BANDIT_PATH = Path("data") / "bandit_state.json"

BANDIT_STATE_PATH: Path = Path(_BANDIT_PATH)

from utils.json_utils import load_json, save_json  # uses your locking/logging

_BIAS = "__bias__"

def _safe_float(x) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return v
    except Exception:
        return 0.0

def _load() -> Dict:
    st = load_json(BANDIT_STATE_PATH, default_type=dict)
    if not isinstance(st, dict):
        st = {}
    st.setdefault("weights", {})
    st.setdefault("counts", {})
    return st

def _save(state: Dict) -> None:
    BANDIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_json(BANDIT_STATE_PATH, state)

def _dot(a: Dict[str, float], b: Dict[str, float]) -> float:
    total = 0.0
    for k, v in b.items():
        total += _safe_float(a.get(k, 0.0)) * _safe_float(v)
    return total

def _with_bias(features: Optional[Dict[str, float]]) -> Dict[str, float]:
    f = dict(features or {})
    f.setdefault(_BIAS, 1.0)
    return f

def choose(actions: List[str], features: Optional[Dict[str, float]] = None, epsilon: float = 0.1) -> str:
    """Pick an action via epsilon-greedy on a linear score w·x."""
    if not actions:
        raise ValueError("choose() requires a non-empty actions list")
    st = _load()
    epsilon = min(1.0, max(0.0, float(epsilon)))
    feats = _with_bias(features)

    # Explore
    if random.random() < epsilon:
        return random.choice(actions)

    # Exploit
    best = None
    best_score = -float("inf")
    for a in actions:
        w = st["weights"].get(a, {})
        score = _dot(w, feats)
        if score > best_score:
            best_score = score
            best = a

    return best if best is not None else random.choice(actions)

def update(
    action: str,
    features: Optional[Dict[str, float]],
    reward: float,
    lr: float = 0.1,
    l2: float = 0.001,
) -> None:
    """
    Update weights with linear step: w <- (1-l2)*w + lr * reward * x
    - Adds a bias feature automatically.
    - Clamps lr and reward to stable ranges.
    """
    if not action:
        return

    st = _load()
    w = dict(st["weights"].get(action, {}))

    lr = min(1.0, max(0.0, float(lr)))
    reward = max(-1.0, min(1.0, _safe_float(reward)))
    l2 = max(0.0, float(l2))
    feats = _with_bias(features)

    if l2 > 0.0 and w:
        for k in list(w.keys()):
            w[k] = _safe_float(w.get(k, 0.0)) * (1.0 - l2)

    for k, v in feats.items():
        w[k] = _safe_float(w.get(k, 0.0)) + lr * reward * _safe_float(v)

    st["weights"][action] = w
    st["counts"][action] = int(st["counts"].get(action, 0)) + 1
    _save(st)

def get_state() -> Dict:
    """Return the current bandit state."""
    return _load()

def reset_state() -> None:
    """Delete the persisted bandit state file."""
    try:
        if BANDIT_STATE_PATH.exists():
            BANDIT_STATE_PATH.unlink()
    except Exception:
        pass