from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Union
from pathlib import Path

from utils.json_utils import load_json, save_json
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    EMOTIONAL_STATE_FILE as _EMOTIONAL_STATE_FILE,
    FEEDBACK_LOG_JSON as _FEEDBACK_LOG_JSON,
    LAST_TAGS as _LAST_TAGS_KEY,
    REWARD_TRACE as _REWARD_TRACE_KEY,
    REWARD_TRACE_JSON as _REWARD_TRACE_JSON,
)

def _as_path(p: Union[str, Path]) -> Path:
    return p if isinstance(p, Path) else Path(p)

EMOTIONAL_STATE_FILE: Path = _as_path(_EMOTIONAL_STATE_FILE)
FEEDBACK_LOG_JSON: Path = _as_path(_FEEDBACK_LOG_JSON)
REWARD_TRACE_JSON: Path = _as_path(_REWARD_TRACE_JSON)

# Use string keys inside the transient reward context to avoid using Path objects as keys
_LAST_TAGS = str(_LAST_TAGS_KEY)
_REWARD_TRACE = str(_REWARD_TRACE_KEY)

def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def log_feedback(
    goal: str,
    result: Union[str, Dict[str, Any]],
    emotion: str = "neutral",
    agent: str = "Orrin",
    score: Union[float, int, None] = None,
    file: Union[str, Path] = FEEDBACK_LOG_JSON,
) -> None:
    """
    Append a feedback entry and propagate a simple reward signal.

    - Persists to FEEDBACK_LOG_JSON.
    - Loads/saves emotional state and reward trace files.
    - Never raises: errors are swallowed to keep telemetry non-fatal.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()

        # 1) Persist feedback entry
        entry = {
            "goal": str(goal),
            "result": result,
            "agent": str(agent),
            "emotion": str(emotion),
            "timestamp": now,
        }
        if score is not None:
            entry["score"] = _to_float(score)

        feedback_log: List[dict] = load_json(file, default_type=list)
        feedback_log.append(entry)
        save_json(file, feedback_log)

        # 2) Prepare reward context (in-memory structure)
        #    Use string keys (not Path objects) for robustness.
        emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
        reward_trace = load_json(REWARD_TRACE_JSON, default_type=list)

        ctx: Dict[str, Any] = {
            "emotional_state": emotional_state,
            _REWARD_TRACE: reward_trace,
            _LAST_TAGS: [str(goal), str(agent)],
        }

        # 3) Decide reward channel & magnitude
        result_str = str(result).lower() if not isinstance(result, str) else result.lower()

        # If no explicit score, assign a reasonable default
        if score is None:
            if any(k in result_str for k in ("success", "helpful", "insightful", "effective")):
                actual = 0.8
            elif any(k in result_str for k in ("failure", "unhelpful", "useless", "error")):
                actual = 0.1
            else:
                actual = 0.4
        else:
            actual = _to_float(score, 0.0)

        actual = _clamp01(actual)
        expected = 0.6
        effort = 0.5

        if any(k in result_str for k in ("success", "helpful", "insightful", "effective", "ok", "done")):
            signal_type = "dopamine"
            mode = "phasic"
        elif any(k in result_str for k in ("failure", "unhelpful", "useless", "error")):
            signal_type = "dopamine"
            mode = "phasic"
        else:
            signal_type = "serotonin"
            mode = "tonic"

        # 4) Emit reward signal; handle mutate-or-return styles
        new_ctx = release_reward_signal(
            ctx,
            signal_type=signal_type,
            actual_reward=actual,
            expected_reward=expected,
            effort=effort,
            mode=mode,
        ) or ctx  # in case the function mutates-in-place and returns None

        # 5) Persist mutated state
        save_json(EMOTIONAL_STATE_FILE, new_ctx.get("emotional_state", emotional_state))
        save_json(REWARD_TRACE_JSON, new_ctx.get(_REWARD_TRACE, reward_trace))

    except Exception:
        # Telemetry should never break the main flow
        pass