# utils/signal_utils.py
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        x = 0.0
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

def _as_tags(tags: Optional[List[Any]]) -> List[str]:
    if not isinstance(tags, list):
        return []
    out: List[str] = []
    for t in tags:
        try:
            out.append(str(t))
        except Exception:
            pass
    return out

def create_signal(
    source: str,
    content: Any,
    signal_strength: float = 0.5,
    tags: Optional[List[Any]] = None,
    novelty: float = 0.0,
) -> Dict[str, Any]:
    """
    Create a standardized, serialization-safe signal dictionary.
    - content is coerced to str
    - signal_strength and novelty are clamped to [0, 1]
    - tags becomes a list[str]
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "content": str(content),
        "signal_strength": _clamp01(signal_strength),
        "tags": _as_tags(tags),
        "novelty": _clamp01(novelty),
    }

def gather_signals(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Collect lightweight signals from subsystems.
    Safe with missing/partial context structures.
    """
    signals: List[Dict[str, Any]] = []

    # Working memory check
    if not context.get("working_memory"):
        signals.append(
            create_signal(
                source="working_memory",
                content="Working memory is empty.",
                signal_strength=0.3,
                tags=["confusion", "low_data"],
                novelty=0.4,
            )
        )

    # Long memory check
    if not context.get("long_memory"):
        signals.append(
            create_signal(
                source="long_memory",
                content="Long-term memory is missing.",
                signal_strength=0.4,
                tags=["anxiety", "uncertainty"],
                novelty=0.5,
            )
        )

    # Emotional spikes (support both shapes)
    emo_state = context.get("emotional_state") or {}
    core = emo_state.get("core_emotions")
    emo_iter = core.items() if isinstance(core, dict) else (
        (k, v) for k, v in emo_state.items() if isinstance(v, (int, float))
    )

    for emotion, value in emo_iter:
        try:
            v = float(value)
        except Exception:
            continue
        if v > 0.6:
            signals.append(
                create_signal(
                    source="emotion",
                    content=f"Emotion '{emotion}' is elevated at {round(v, 3)}.",
                    signal_strength=_clamp01(v),
                    tags=["emotion", str(emotion)],
                    novelty=random.uniform(0.1, 0.6),
                )
            )

    return signals