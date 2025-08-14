# introspection.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.json_utils import load_json, save_json, extract_json
from utils.self_model import get_self_model, ensure_self_model_integrity
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_activity, log_private, log_model_issue
from utils.log_reflection import log_reflection
from cognition.planning.motivations import update_motivations
from cognition.planning.reflection import (
    reflect_on_growth_history,
    reflect_on_effectiveness,
    reflect_on_missed_goals,
)
from memory.working_memory import update_working_memory
# You import evolution helpers elsewhere if you use them here later:
# from cognition.planning.evolution import simulate_future_selves, plan_self_evolution
from paths import (
    DEBUG_FAILED_GOAL_RESPONSE_JSON,
    GOALS_FILE,
    LONG_MEMORY_FILE,
    PRIVATE_THOUGHTS_FILE,
    MODEL_CONFIG_FILE,
)

def _coerce_list(x) -> List[Any]:
    if isinstance(x, list):
        return x
    if x is None:
        return []
    return [x]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def introspective_planning() -> Dict[str, Any]:
    raw = None  # for debug write on failure
    try:
        # Refresh motivations based on your pipeline
        update_motivations()

        # Load current context
        current_goals = _coerce_list(load_json(GOALS_FILE, default_type=list))
        long_memory   = _coerce_list(load_json(LONG_MEMORY_FILE, default_type=list))
        self_model    = ensure_self_model_integrity(get_self_model())

        # Reflections
        growth  = reflect_on_growth_history(long_memory)
        effective = reflect_on_effectiveness(current_goals, long_memory)
        missed  = reflect_on_missed_goals(current_goals, long_memory)

        # Model config (defensive)
        cfg = load_json(MODEL_CONFIG_FILE, default_type=dict)
        thinking_cfg = {}
        if isinstance(cfg, dict):
            thinking_cfg = dict(cfg.get("thinking", {})) if isinstance(cfg.get("thinking"), dict) else {}
        thinking_cfg["model"] = get_thinking_model()

        # Keep prompt bounded
        goals_for_prompt = current_goals[:100]  # cap if needed
        prompt = (
            "You are Orrin's planning cortex. Given the following context, propose an updated goal list.\n\n"
            f"Current goals (JSON):\n{json.dumps(goals_for_prompt, ensure_ascii=False)[:4000]}\n\n"
            f"Growth reflection:\n{growth}\n\n"
            f"Effectiveness reflection:\n{effective}\n\n"
            f"Missed goals reflection:\n{missed}\n\n"
            'Return a JSON object with fields: {"updated_goals": [], "summary": "short rationale"}.'
        )

        raw = generate_response(prompt, config=thinking_cfg) or ""
        # Prefer tolerant extractor; fall back to strict loads
        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {}

        updated = _coerce_list(parsed.get("updated_goals", current_goals))
        summary = str(parsed.get("summary", "")).strip() or "No summary provided."

        # Persist
        save_json(GOALS_FILE, updated)
        update_working_memory("🧠 Introspective planning updated goal hierarchy.")
        log_activity("✅ Introspective planning complete.")
        log_reflection(f"Self-belief reflection summary: {summary}")

        # Single-line private thought (keeps your line parser happy)
        with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{_now()}] Updated goals (count={len(updated)}). Summary: {summary}\n")

        return {"updated_goals": updated, "summary": summary}

    except Exception as e:
        log_model_issue(f"[introspective_planning] Exception: {e}")
        update_working_memory("⚠️ Introspective planning failed.")
        try:
            with open(DEBUG_FAILED_GOAL_RESPONSE_JSON, "w", encoding="utf-8") as f:
                f.write(raw if isinstance(raw, str) else "[no raw]")
        except Exception:
            pass
        # Fall back to last known goals
        return {
            "updated_goals": _coerce_list(load_json(GOALS_FILE, default_type=list)),
            "summary": "error",
        }