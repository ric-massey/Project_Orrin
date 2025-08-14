from __future__ import annotations

import math
import random
from typing import Dict, Any, Iterable, List
from pathlib import Path

from paths import FUNCTION_BANDIT_JSON, bandit_path
from utils.json_utils import load_json, save_json

# Global bandit state file (already a Path from paths.py)
FILE: Path = FUNCTION_BANDIT_JSON

# --- Global (non-contextual) bandit ------------------------------------------

def _load() -> Dict[str, Dict[str, Any]]:
    data = load_json(FILE, default_type=dict)
    return data if isinstance(data, dict) else {}

def _save(data: Dict[str, Dict[str, Any]]) -> None:
    save_json(FILE, data)

def record_outcome(name: str, reward: float) -> None:
    data = _load()
    st = data.setdefault(name, {"n": 0, "r": 0.0})
    st["n"] += 1
    st["r"] += float(reward)
    _save(data)

def ucb1(scores: Dict[str, Dict[str, Any]], total: int) -> Dict[str, float]:
    out: Dict[str, float] = {}
    total = max(total, 2)
    for name, st in scores.items():
        n = max(1, int(st.get("n", 0)))
        r = float(st.get("r", 0.0))
        avg = r / n
        bonus = math.sqrt(2.0 * math.log(total) / n)
        out[name] = avg + bonus
    return out

def pick(candidate_names: Iterable[str]) -> List[str]:
    names = list(dict.fromkeys(str(n) for n in candidate_names if n))  # dedupe/clean
    if not names:
        return []
    data = _load()
    total = sum(int(v.get("n", 0)) for v in data.values()) + 1
    scores = {n: data.get(n, {"n": 0, "r": 0.0}) for n in names}
    ranked = sorted(ucb1(scores, total).items(), key=lambda x: (-x[1], x[0]))
    return [n for n, _ in ranked]


# --- Contextual bandit (per-context UCB1 with epsilon) -----------------------

def _ctx_file(ctx: str) -> Path:
    # bandit_path(ctx) already returns a Path pointing into DATA_DIR
    return bandit_path(ctx)

def _load_ctx(ctx: str) -> Dict[str, Dict[str, Any]]:
    data = load_json(_ctx_file(ctx), default_type=dict)
    return data if isinstance(data, dict) else {}

def _save_ctx(ctx: str, data: Dict[str, Dict[str, Any]]) -> None:
    save_json(_ctx_file(ctx), data)

def record_outcome_ctx(ctx: str, name: str, reward: float) -> None:
    data = _load_ctx(ctx)
    st = data.setdefault(name, {"n": 0, "r": 0.0})
    st["n"] += 1
    st["r"] += float(reward)
    _save_ctx(ctx, data)

def pick_ctx(ctx: str, candidates: Iterable[str], epsilon: float = 0.08) -> List[str]:
    names = list(dict.fromkeys(str(c) for c in candidates if c))
    if not names:
        return []
    epsilon = max(0.0, min(1.0, float(epsilon)))

    data = _load_ctx(ctx)

    if random.random() < epsilon:
        shuffled = names[:]
        random.shuffle(shuffled)
        return shuffled

    total = sum(int(v.get("n", 0)) for v in data.values()) + 1

    def score(name: str) -> float:
        s = data.get(name, {"n": 0, "r": 0.0})
        n = max(1, int(s.get("n", 0)))
        avg = float(s.get("r", 0.0)) / n
        bonus = math.sqrt(2.0 * math.log(max(total, 2)) / n)
        return avg + bonus

    return sorted(names, key=lambda nm: (-score(nm), nm))