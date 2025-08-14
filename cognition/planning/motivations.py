# motivations.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.json_utils import load_json, save_json, extract_json
from utils.self_model import get_self_model, save_self_model, ensure_self_model_integrity
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_model_issue
from memory.working_memory import update_working_memory
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    GOAL_TRAJECTORY_LOG_JSON,
    FEEDBACK_LOG,
    LONG_MEMORY_FILE,
    LOG_FILE,
    PRIVATE_THOUGHTS_FILE,
    ACTION_FILE,
)

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# -------------------------
# Motivation updates
# -------------------------

def update_motivations() -> None:
    """
    Reflect on recent thoughts and core values, revise motivations in self_model.
    """
    try:
        self_model = ensure_self_model_integrity(get_self_model())
        if not isinstance(self_model, dict):
            raise ValueError("self_model not a dict")

        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        if not isinstance(long_memory, list):
            long_memory = []

        recent = [
            m.get("content")
            for m in long_memory[-15:]
            if isinstance(m, dict) and isinstance(m.get("content"), str)
        ]
        core_values = self_model.get("core_values", [])
        current_motivations = self_model.get("motivations", [])

        context = (
            "Recent reflections:\n" + "\n".join(f"- {r}" for r in recent) + "\n\n"
            "Current motivations:\n" + "\n".join(f"- {m}" for m in current_motivations) + "\n\n"
            "Core values:\n" +
            "\n".join(
                f"- {v['value']}" if isinstance(v, dict) and "value" in v else f"- {v}"
                for v in core_values
            )
        )

        prompt = (
            f"{context}\n\n"
            "Reflect and revise:\n"
            "- Remove misaligned motivations\n"
            "- Add any new ones inspired by recent reflections or values\n"
            "Return JSON ONLY in this format:\n"
            "{\n"
            '  "updated_motivations": ["", ""],\n'
            '  "reasoning": ""\n'
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()}) or ""
        result = extract_json(response)

        if not isinstance(result, dict) or "updated_motivations" not in result:
            raise ValueError("Missing or invalid `updated_motivations` in result.")

        upd = result.get("updated_motivations")
        if not isinstance(upd, list):
            raise ValueError("`updated_motivations` must be a list.")

        self_model["motivations"] = upd
        save_self_model(self_model)

        update_working_memory("🧭 Motivations updated: " + ", ".join(map(str, upd)))
        # Write a single-line entry for your line-based parser
        with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{_utc_now()}] Revised motivations: {result.get('reasoning','')}\n")

    except Exception as e:
        log_model_issue(f"[update_motivations] Motivation update failed: {e}")
        update_working_memory("⚠️ Failed to update Orrin's motivations.")

# -------------------------
# Priority adjustment
# -------------------------

def adjust_priority(goal: Dict[str, Any], fb: Dict[str, Any]) -> None:
    result_text = str(fb.get("result", "")).lower()
    emotion = str(fb.get("emotion", "neutral")).lower()
    goal["priority"] = int(goal.get("priority", 5))

    reward = 0.0
    if any(w in result_text for w in ["success", "helpful", "insightful", "effective"]):
        if emotion in {"joy", "excited", "grateful"}:
            goal["priority"] = min(10, goal["priority"] + 2)
            reward = 1.0
        elif emotion in {"satisfied", "curious"}:
            goal["priority"] = min(10, goal["priority"] + 1)
            reward = 0.8

    elif any(w in result_text for w in ["fail", "unhelpful", "repetitive", "useless"]):
        if emotion in {"frustrated", "angry", "ashamed"}:
            goal["priority"] = max(1, goal["priority"] - 2)
            reward = 0.3
        elif emotion in {"bored", "disappointed"}:
            goal["priority"] = max(1, goal["priority"] - 1)
            reward = 0.4

    release_reward_signal(
        context={},  # no rich context here; pass if available
        signal_type="dopamine",
        actual_reward=reward,
        expected_reward=0.7,
        effort=float(goal.get("effort", 0.5)),
        mode="phasic",
        source="adjusted priority",
    )

# -------------------------
# Goal weights adjustment
# -------------------------

def adjust_goal_weights(context: Dict[str, Any] | None = None) -> None:
    """
    Use recent feedback to nudge priorities on upcoming actions/goals.
    Writes trajectory snapshots to GOAL_TRAJECTORY_LOG_JSON.
    """
    feedback = load_json(FEEDBACK_LOG, default_type=list)
    if not isinstance(feedback, list) or not feedback:
        return

    next_actions = load_json(ACTION_FILE, default_type=dict)
    if not isinstance(next_actions, (dict, list)):
        next_actions = {}

    trajectory_log = load_json(GOAL_TRAJECTORY_LOG_JSON, default_type=dict)
    if not isinstance(trajectory_log, dict):
        trajectory_log = {}

    now = _utc_now()
    recent_feedback = [fb for fb in feedback[-10:] if isinstance(fb, dict)]

    # Flatten next_actions (supports dict by tiers or a flat list)
    all_goals: List[Dict[str, Any]] = []
    if isinstance(next_actions, dict):
        for tier in ("short_term", "mid_term", "long_term"):
            items = next_actions.get(tier)
            if isinstance(items, list):
                all_goals.extend(g for g in items if isinstance(g, dict))
    elif isinstance(next_actions, list):
        all_goals = [g for g in next_actions if isinstance(g, dict)]

    for goal in all_goals:
        name = goal.get("name")
        if not isinstance(name, str) or not name:
            continue
        for fb in recent_feedback:
            if str(fb.get("goal", "")) == name:
                adjust_priority(goal, fb)
        trajectory_log.setdefault(name, []).append({
            "timestamp": now,
            "priority": int(goal.get("priority", 5)),
            "tier": goal.get("tier", "unknown"),
        })

    # Persist updates
    save_json(ACTION_FILE, next_actions)
    save_json(GOAL_TRAJECTORY_LOG_JSON, trajectory_log)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] Adjusted goal priorities and released reward signals based on feedback.\n")