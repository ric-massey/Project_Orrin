from __future__ import annotations
from typing import Dict, Any

def context_key(context: Dict[str, Any]) -> str:
    emo_state = context.get("emotional_state") or {}
    core = emo_state.get("core_emotions") if isinstance(emo_state, dict) else {}
    if isinstance(core, dict) and core:
        try:
            dom = max(core.items(), key=lambda kv: kv[1])[0]
        except Exception:
            dom = "neutral"
    else:
        dom = emo_state.get("dominant", "neutral") if isinstance(emo_state, dict) else "neutral"

    goal_ctx = (context.get("committed_goal") or {}) or (context.get("focus_goal") or {})
    goal_tier = goal_ctx.get("tier", "none") if isinstance(goal_ctx, dict) else "none"

    mode_val = context.get("mode", "default")
    if isinstance(mode_val, dict):
        mode = mode_val.get("mode", "default")
    else:
        mode = str(mode_val)

    # Avoid delimiter collisions
    dom = str(dom).replace("|", "/")
    goal_tier = str(goal_tier).replace("|", "/")
    mode = str(mode).replace("|", "/")

    return f"{dom}|{goal_tier}|{mode}"