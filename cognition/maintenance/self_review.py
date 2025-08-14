# self_review.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.events_miner import last_n_events, summarize_outcomes
from utils.log_reflection import log_reflection
from utils.json_utils import load_json, save_json
from utils.log import log_error
from utils.append import append_to_json
from paths import LONG_MEMORY_FILE

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def periodic_self_review(n_events: int = 400) -> None:
    try:
        evts = last_n_events(n_events)
        if not isinstance(evts, list):
            log_error("periodic_self_review: last_n_events did not return a list; using empty list.")
            evts = []

        agg = summarize_outcomes(evts) or {}
        accepted = agg.get("accepted", 0)
        total = agg.get("total", len(evts))
        top = agg.get("top", [])

        note = (
            f"[Self-Review {_utc_now()}] "
            f"Accepted {accepted}/{total} "
            f"Top picks: {top}"
        )

        # Log reflective note
        log_reflection(note, reflection_type="self_review")

        # Append a single record into long memory (safer than read-modify-write)
        append_to_json(LONG_MEMORY_FILE, {
            "timestamp": _utc_now(),
            "content": note,
            "tags": ["self_review", "summary"],
        })

    except Exception as e:
        log_error(f"periodic_self_review ERROR: {e}")