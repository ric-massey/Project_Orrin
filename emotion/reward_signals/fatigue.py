# fatigue.py
import time
import random
import math
from typing import Dict, Any

def update_function_fatigue(context: Dict[str, Any], function_name: str) -> None:
    """
    Updates in-place:
      context["function_fatigue"][function_name] = {
        last_used, count, score (0..10), fatigue_history
      }
    Decay is per-minute and speeds up when motivation/excitement are high.
    """
    fatigue = context.setdefault("function_fatigue", {})
    now = time.time()
    info = fatigue.get(function_name, {"last_used": 0, "count": 0, "score": 0.0, "fatigue_history": []})

    # Seconds since last use
    dt = max(0.0, now - float(info.get("last_used", 0.0)))

    # Mood-based decay modulation: higher motivation/excitement => faster recovery (more decay)
    emotional_state = context.get("emotional_state", {}) or {}
    motivation = float(emotional_state.get("motivation", 0.5))
    excitement = float(emotional_state.get("excitement", 0.0))
    mood_factor = 1.0 + 0.3 * (motivation + excitement)
    mood_factor = max(0.5, min(mood_factor, 1.5))  # clamp both ways

    # Nonlinear decay rate rises with fatigue level
    decay_rate_base = 0.12  # per-minute-ish base
    fatigue_level = float(info.get("score", 0.0))
    nonlinear_decay = decay_rate_base * math.log1p(max(0.0, fatigue_level))  # fix: no +1 inside log1p
    decay_rate = nonlinear_decay * mood_factor

    # Exponential decay by elapsed minutes
    fatigue_after_decay = fatigue_level * math.exp(-decay_rate * (dt / 60.0))

    # Recovery boost if long rest
    if dt > 600:  # 10 minutes
        fatigue_after_decay *= 0.85

    # Fatigue gain for this use (sometimes “push through”)
    push_through_factor = 0.5 if random.random() < 0.1 else 1.0
    fatigue_gain = 1.0 * push_through_factor

    new_fatigue = fatigue_after_decay + fatigue_gain

    # Short history to smooth/detect trends
    hist = list(info.get("fatigue_history", []))
    hist.append((now, new_fatigue))
    if len(hist) > 30:
        hist = hist[-30:]

    info.update({
        "last_used": now,
        "count": int(info.get("count", 0)) + 1,
        "score": min(new_fatigue, 10.0),
        "fatigue_history": hist,
    })
    fatigue[function_name] = info
    context["function_fatigue"] = fatigue  # explicit

def fatigue_penalty(context: Dict[str, Any], function_name: str) -> float:
    """
    Returns a *negative* multiplier-style penalty in [-0.6, 0],
    modulated by motivation (less negative), anxiety & boredom (more negative).
    """
    fatigue = context.get("function_fatigue", {})
    info = fatigue.get(function_name, {"score": 0.0})
    score = float(info.get("score", 0.0))

    # Base penalty scales 0 (no fatigue) to -0.6
    base_penalty = -0.6 * min(1.0, score / 7.0)

    emotional_state = context.get("emotional_state", {}) or {}
    motivation = float(emotional_state.get("motivation", 0.5))
    anxiety = float(emotional_state.get("anxiety", 0.0))
    boredom = float(emotional_state.get("boredom", 0.3))

    # Motivation reduces penalty, anxiety/boredom increase it
    motivation_factor = 1 - 0.7 * motivation
    anxiety_factor = 1 + 0.5 * anxiety
    boredom_factor = 1 + 0.4 * boredom

    penalty = base_penalty * motivation_factor * anxiety_factor * boredom_factor

    # 5% chance to ignore fatigue entirely
    if random.random() < 0.05:
        penalty = 0.0

    return float(penalty)

def fatigue_penalty_from_context(emotional_state: Dict[str, float], action_type: str) -> float:
    """
    Returns a *positive* penalty in [0.0, 1.0] based on emotional fatigue/stress/overwhelm
    (Note: unit differs from fatigue_penalty above; callers should not mix them directly.)
    """
    fatigue_level = float(emotional_state.get("fatigue", 0.0))
    stress = float(emotional_state.get("stress", 0.0))
    overwhelm = float(emotional_state.get("overwhelm", 0.0))

    # Weighted blend
    fatigue_score = fatigue_level * 0.6 + stress * 0.3 + overwhelm * 0.1

    # Higher penalty for demanding actions
    if action_type in {"physical", "complex", "long_task", "creative"}:
        fatigue_score *= 1.5

    return max(0.0, min(fatigue_score, 1.0))