from __future__ import annotations

from typing import Dict, Any
from utils.json_utils import save_json, load_json
from memory.working_memory import update_working_memory
from paths import EMOTIONAL_STATE_FILE

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

def apply_emotional_feedback(cognition_name: str, score: float) -> Dict[str, Any]:
    """
    Nudge core emotions based on a cognition's outcome score.

    - score ∈ [-1, 1]
      • ≥ 0.5 → increase 'happiness'
      • ≤ -0.5 → increase 'frustration'
      • |score| < 0.2 → mild 'confusion' tick

    Returns the updated emotional_state dict.
    """
    # Load current state safely
    emotional_state: Dict[str, Any] = load_json(EMOTIONAL_STATE_FILE, default_type=dict) or {}
    core: Dict[str, float] = dict(emotional_state.get("core_emotions", {}))

    # Normalize inputs
    try:
        score = float(score)
    except Exception:
        score = 0.0
    score = _clamp(score, -1.0, 1.0)

    # Baseline defaults if missing
    if "happiness" not in core:
        core["happiness"] = 0.5
    if "frustration" not in core:
        core["frustration"] = 0.0
    if "confusion" not in core:
        core["confusion"] = 0.0

    # Modest, bounded deltas
    if score >= 0.5:
        core["happiness"] = _clamp(core["happiness"] + 0.25 * score)
    elif score <= -0.5:
        core["frustration"] = _clamp(core["frustration"] + 0.25 * abs(score))
    elif abs(score) < 0.2:
        core["confusion"] = _clamp(core["confusion"] + 0.05)

    emotional_state["core_emotions"] = core
    save_json(EMOTIONAL_STATE_FILE, emotional_state)

    update_working_memory(
        {
            "content": f"Emotional feedback for '{cognition_name}': score={score:.2f} → "
                       f"happiness={core['happiness']:.2f}, frustration={core['frustration']:.2f}, "
                       f"confusion={core['confusion']:.2f}",
            "event_type": "emotion_feedback",
            "importance": 1,
            "priority": 1,
        }
    )

    return emotional_state