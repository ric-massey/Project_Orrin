# reward_spike.py
from datetime import datetime, timezone
from utils.log import log_private
from typing import Iterable, Optional
import random

_PHRASES = [
    "A noticeable surge of",
    "An unexpected rise in",
    "A clear spike in",
    "A subtle increase of",
    "A strong wave of",
    "A sudden boost in",
    "A marked increase in",
]

_REFLECTIONS = {
    "dopamine": "This suggests rising motivation and confidence.",
    "novelty": "Curiosity seems to have been triggered by something new.",
    "serotonin": "Indications of improved emotional stability.",
    "connection": "Strengthening of social or emotional bonds detected.",
    "reward_impulse": "An impulse has been triggered, prompting action.",
}

def _intensity_label(strength: float) -> str:
    if strength > 0.8:
        return "intense"
    if strength > 0.5:
        return "strong"
    if strength > 0.2:
        return "moderate"
    return "slight"

def _coerce_tags(tags: Optional[Iterable]) -> list[str]:
    if not tags:
        return []
    return [str(t) for t in tags if t is not None]

def log_reward_spike(signal_type: str = "dopamine", strength: float = 1.0, tags: Optional[Iterable] = None) -> None:
    """
    Log a human-readable reward spike note via utils.log.log_private.
    - signal_type: e.g., 'dopamine', 'novelty', 'serotonin', 'connection'
    - strength: arbitrary positive float; will be clamped to [0, 1.5] for display
    - tags: optional iterable of tags; coerced to strings
    """
    ts = datetime.now(timezone.utc).isoformat()
    signal = str(signal_type or "unknown")
    # soft clamp just for nicer logs; avoids exploding numbers
    s_val = max(0.0, min(float(strength or 0.0), 1.5))

    phrase = random.choice(_PHRASES)
    intensity = _intensity_label(s_val)
    tag_list = _coerce_tags(tags)

    message = f"{phrase} {signal} detected ({intensity} signal, strength {s_val:.2f})."
    if tag_list:
        message += f" Tags observed: {', '.join(tag_list)}."

    reflection = _REFLECTIONS.get(signal.lower())
    if reflection:
        message += " " + reflection

    log_private(f"[{ts}] {message}")