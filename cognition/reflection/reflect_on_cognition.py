# cognition/cognition_schedule.py
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from typing import Any, Dict, List, Optional

from memory.working_memory import update_working_memory
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from utils.json_utils import load_json, save_json
from utils.error_router import catch_and_route

from paths import (
    COGN_SCHEDULE_FILE,
    COGNITION_HISTORY_FILE,
    LOG_FILE,
    PRIVATE_THOUGHTS_FILE,
)

__all__ = ["update_cognition_schedule", "reflect_on_cognition_patterns"]


# --- small numeric helper (inline fallback) ---------------------------------
try:
    from utils.num import safe_float  # type: ignore
except Exception:  # pragma: no cover
    def safe_float(x: Any, default: float = 0.0) -> float:
        try:
            return float(x)
        except Exception:
            try:
                # if dict-like, sum numeric values (common “score” shapes)
                vals = x.values() if hasattr(x, "values") else []
                return sum(float(v) for v in vals)
            except Exception:
                return default


# --- path helper ------------------------------------------------------------
def _ensure_parent(p: str | Path) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)


# === API ====================================================================

@catch_and_route("cognition", return_on_error=lambda e: None)
def update_cognition_schedule(new_schedule: Dict[str, Any]) -> Optional[bool]:
    """
    Merge a partial schedule dict into the persisted cognition schedule.
    Returns:
      True  -> changes were applied
      False -> no meaningful change
      None  -> bad input or routed error
    """
    if not isinstance(new_schedule, dict):
        log_error(f"update_cognition_schedule: new_schedule must be dict, got {type(new_schedule)}")
        update_working_memory("⚠️ Ignored cognition schedule update (bad format).")
        return None

    current = load_json(COGN_SCHEDULE_FILE, default_type=dict)
    if not isinstance(current, dict):
        current = {}

    previous = dict(current)
    current.update(new_schedule)
    save_json(COGN_SCHEDULE_FILE, current)

    diff = {
        k: (previous.get(k), current.get(k))
        for k in set(previous) | set(new_schedule)
        if previous.get(k) != current.get(k)
    }

    # Append human-readable traces
    _ensure_parent(LOG_FILE)
    with Path(LOG_FILE).open("a", encoding="utf-8") as f:
        f.write(
            f"\n[{datetime.now(timezone.utc)}] Cognition schedule updated:\n"
            f"{json.dumps(new_schedule, indent=2, ensure_ascii=False)}\n"
        )

    _ensure_parent(PRIVATE_THOUGHTS_FILE)
    with Path(PRIVATE_THOUGHTS_FILE).open("a", encoding="utf-8") as f:
        f.write(
            f"\n[{datetime.now(timezone.utc)}] Orrin updated his cognition rhythm based on perceived needs.\n"
        )

    if diff:
        log_private(f"Schedule diff after manual update:\n{json.dumps(diff, indent=2, ensure_ascii=False)}")
        update_working_memory("Cognition schedule updated.")
        return True

    update_working_memory("No meaningful changes to cognition schedule.")
    return False


@catch_and_route("cognition", return_on_error=lambda e: None)
def reflect_on_cognition_patterns(n: int = 50) -> Optional[str]:
    """
    Analyze recent cognition history to identify usage patterns, over/under-used functions,
    and shifting focus. Returns the plain-text summary on success; None on no data/error.
    """
    history = load_json(COGNITION_HISTORY_FILE, default_type=list)
    if not isinstance(history, list) or not history:
        update_working_memory("⚠️ No cognition history to reflect on.")
        return None

    # Defensive: n might be passed as non-int; also guard negative values
    try:
        n = max(1, int(n))
    except Exception:
        n = 50

    recent_history = history[-n:]
    usage: Counter[str] = Counter()
    satisfaction_by_fn: Dict[str, float] = {}
    count_by_fn: Dict[str, int] = {}

    for entry in recent_history:
        if not isinstance(entry, dict):
            continue

        # function id can arrive under different keys/shapes
        fn_raw = entry.get("function", entry.get("choice", ""))
        if isinstance(fn_raw, (list, tuple)):
            fn = ", ".join(str(x) for x in fn_raw)
        elif isinstance(fn_raw, dict):
            fn = fn_raw.get("name") or fn_raw.get("type") or json.dumps(fn_raw, ensure_ascii=False)[:60]
        else:
            fn = str(fn_raw)

        score = safe_float(entry.get("satisfaction", 0.0), 0.0)

        if fn:
            usage[fn] += 1
            satisfaction_by_fn[fn] = satisfaction_by_fn.get(fn, 0.0) + score
            count_by_fn[fn] = count_by_fn.get(fn, 0) + 1

    top_functions = usage.most_common(5)
    rare_functions = [fn for fn, count in usage.items() if count == 1]

    satisfaction_summary = {
        fn: round(satisfaction_by_fn[fn] / max(1, count_by_fn.get(fn, 0)), 2)
        for fn in satisfaction_by_fn
    }

    lines: List[str] = [
        f"🧠 Cognition pattern summary over last {min(n, len(history))} cycles:",
        f"- Top used functions: {', '.join(f'{fn} ({count})' for fn, count in top_functions) or 'None'}",
        f"- Rarely used functions: {', '.join(rare_functions) or 'None'}",
        "- Average satisfaction by function:",
    ]
    for fn, avg in satisfaction_summary.items():
        lines.append(f"  - {fn}: {avg}")

    summary = "\n".join(lines)
    update_working_memory(summary)
    log_private(f"\n[{datetime.now(timezone.utc)}] Reflection on cognition patterns:\n{summary}")
    try:
        log_reflection(f"Self-belief reflection: {summary.strip()}")
    except Exception:
        # don't let logging fail the reflection
        pass

    return summary
