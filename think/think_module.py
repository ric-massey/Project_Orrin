# think/think_module.py
from __future__ import annotations

import time
import json
from typing import Any, Dict, List

from utils.json_utils import load_json
from utils.emotion_utils import dominant_emotion
from utils.log import log_error

from utils.manage_cycle_count import manage_cycle_count
from think.think_utils.dreams_emotional_logic import dreams_and_emotional_logic
from think.think_utils.reflect_on_directive import reflect_on_directive
from think.think_utils.select_function import select_function  # NEW API supports legacy triple if kwargs passed
from think.think_utils.finalize import finalize_cycle
from think.think_utils.execute_cognitive_actions import execute_cognitive_action

from behavior.speak import OrrinSpeaker
from cognition.selfhood.relationships import update_relationship_model
from cognition.selfhood.self_model_conflicts import update_self_model
from emotion.emotion_learning import update_emotion_function_map

from paths import (
    SELF_MODEL_FILE, LONG_MEMORY_FILE, TOOL_REQUESTS_FILE,
    COGNITION_STATE_FILE, COGNITION_HISTORY_FILE, RELATIONSHIPS_FILE,
    COGNITIVE_FUNCTIONS_LIST_FILE,  # ← from paths (not registry)
)


def _load_available_functions() -> List[str]:
    names = load_json(COGNITIVE_FUNCTIONS_LIST_FILE, default_type=list)
    if not isinstance(names, list):
        return []
    # coerce to simple list[str]
    out: List[str] = []
    for it in names:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict) and "name" in it:
            out.append(str(it["name"]))
    return out


def think(context: Dict[str, Any]) -> Dict[str, Any]:
    cycle_start_time = time.perf_counter()

    try:
        # === 0) Manage cycle count & defaults ===
        context, cycle_count = manage_cycle_count(context)
        context.setdefault("committed_goal", None)
        context.setdefault("action_debt", 0)
        context.setdefault("act_now", False)
        context.setdefault("reflection_budget_exhausted", False)
        context.setdefault("recent_picks", [])  # NEW: track choices for boredom/novelty
        context.pop("minimum_viable_action", None)

        # === 1) Load critical state ===
        self_model      = load_json(SELF_MODEL_FILE,        default_type=dict)
        long_memory     = load_json(LONG_MEMORY_FILE,       default_type=list)
        tool_requests   = load_json(TOOL_REQUESTS_FILE,     default_type=list)
        cognition_state = load_json(COGNITION_STATE_FILE,   default_type=dict)
        cognition_log   = load_json(COGNITION_HISTORY_FILE, default_type=list)
        relationships   = load_json(RELATIONSHIPS_FILE,     default_type=dict)

        context["relationships"] = relationships
        working_memory            = context.get("working_memory", [])
        wm_updater                = context.get("update_working_memory")
        speaker                   = context.get("speaker", OrrinSpeaker(self_model, long_memory))

        # === 2) Dreams & emotional logic ===
        context, emotional_state, amygdala_response = dreams_and_emotional_logic(context)

        # === 3) Signals / attention ===
        top_signals = context.get("top_signals", [])
        attention_mode = context.get("attention_mode", "neutral")
        context["filtered_signals"] = top_signals  # back-compat
        update_relationship_model(context)

        # Act-now nudge if stalled on a committed goal
        try:
            debt = int(context.get("action_debt", 0) or 0)
            if bool(context.get("committed_goal")) and debt >= 2:
                context["act_now"] = True
                context["reflection_budget_exhausted"] = True
                context["discouraged_functions"] = ["reflect", "plan", "analyz", "deliberat"]
                mv = (context["committed_goal"] or {}).get("next_action")
                if isinstance(mv, dict):
                    context["minimum_viable_action"] = mv
                if callable(wm_updater):
                    wm_updater("⏱️ Commit→Act: Reflection budget exhausted; biasing toward action.")
        except Exception:
            pass

        # === 4) Directive reflection (kept as-is) ===
        _ = reflect_on_directive(self_model, context)

        # === 5) Available functions (for transparency/UI only) ===
        context["available_functions"] = context.get("available_functions") or _load_available_functions()

        # === 6) Pick next cognitive function via selector ===
        sel = select_function(context, speaker=speaker, amygdala_response=amygdala_response)

        # Defaults
        fn_name: str = ""
        reason: Dict[str, Any] = {"via": "auto-selected", "candidates": context.get("available_functions", [])}
        is_action: bool = False
        selected_args = None        # CHANGED: capture args if selector provided them
        selected_kwargs = None      # CHANGED: capture kwargs if selector provided them

        if isinstance(sel, tuple) and len(sel) == 3:
            fn_name, reason, is_action = sel
        elif isinstance(sel, str):
            fn_name = sel
        elif isinstance(sel, dict):
            # CHANGED: only treat as an action if it declares a behavior 'type'
            if "type" in sel:
                try:
                    execute_cognitive_action(sel, context)
                    is_action = True
                except Exception:
                    pass
                # even if executed, allow returning the chosen name for logging if present
                fn_name = sel.get("name") or fn_name
            else:
                # Dict-shaped cognition selection: accept name + optional args/kwargs
                fn_name = (sel.get("name") or sel.get("next_function") or "").strip()
                if isinstance(sel.get("args"), (list, tuple)):
                    selected_args = list(sel["args"])
                if isinstance(sel.get("kwargs"), dict):
                    selected_kwargs = dict(sel["kwargs"])

        if not isinstance(fn_name, str) or not fn_name.strip():
            # If selector can’t decide, return no-instruction; ORRIN will fallback
            return {"context": context}

        fn_name = fn_name.strip()

        # NEW: Update boredom based on repetition and track recent picks
        try:
            emo = context.get("emotional_state", {}) or {}
            recent = context.setdefault("recent_picks", [])
            if recent and fn_name == recent[-1]:
                emo["boredom"] = min(1.0, float(emo.get("boredom", 0.0)) + 0.05)
            else:
                emo["boredom"] = max(0.0, float(emo.get("boredom", 0.0)) - 0.03)
            context["emotional_state"] = emo
            recent.append(fn_name)
            if len(recent) > 64:
                del recent[:-32]
        except Exception:
            pass

        # Stash decision metadata on context so downstream executors can learn/reward
        try:
            context["last_decision"] = {
                "picked": fn_name,
                "reason": reason,  # includes features_on, candidates, scores, decision_id (from selector)
                "ts": time.time(),
            }
        except Exception:
            pass

        # Link dominant emotion → function (learning signal)
        dom_emo = dominant_emotion(emotional_state)
        if dom_emo:
            try:
                update_emotion_function_map(dom_emo, fn_name)
            except Exception:
                pass

        # === 7) Basal ganglia: evaluate + maybe act ===
        from think.think_utils.action_gate import evaluate_and_act_if_needed
        _ = evaluate_and_act_if_needed(
            context,
            emotional_state=emotional_state,
            long_memory=long_memory,
            speaker=speaker,
        )

        # === 8) Finalize cycle (pass FULL reason dict) ===
        user_input = context.get("latest_user_input")
        context_hash = hash(str(self_model) + str(emotional_state) + str(long_memory[-5:]))

        # Keep the full reason dict (or wrap a string)
        full_reason = reason if isinstance(reason, dict) else {"note": str(reason), "via": "unknown"}

        # (optional) expose top data back on context for downstream logging
        try:
            context["last_candidates"] = list(full_reason.get("candidates", []))[:12]
            context["last_ranked"] = list(full_reason.get("ranked", []))[:12]
        except Exception:
            pass

        try:
            _ = finalize_cycle(
                context,
                user_input,
                fn_name,
                full_reason,    # <-- pass the full reason dict
                context_hash,
                speaker,
            )
        except Exception:
            pass

        # === 9) Update self model (non-blocking) ===
        try:
            update_self_model()
        except Exception:
            pass

        # === 10) Persist pieces onto context ===
        context["self_model"] = self_model
        context["long_memory"] = long_memory
        context["emotional_state"] = emotional_state
        context["working_memory"] = working_memory
        context["cycle_count"] = cycle_count
        context["last_think_time"] = time.time()
        context["last_cycle_duration"] = time.perf_counter() - cycle_start_time
        context.pop("filtered_signals", None)

        # === 11) Return Orrin-friendly shape (with optional args/kwargs) ===
        if is_action:
            return {"action": {"name": fn_name}, "context": context}

        out = {"next_function": fn_name, "context": context}
        # CHANGED: pass through args/kwargs when provided so ORRIN.py can forward them
        if selected_args is not None:
            out["args"] = selected_args
        if selected_kwargs is not None:
            out["kwargs"] = selected_kwargs
        return out

    except Exception as e:
        # Do not raise here; ORRIN.py has routing/repair. Just annotate context so fallback can proceed.
        log_error(f"THINK() CRASHED: {e}\n{__import__('traceback').format_exc()}")
        context["last_think_error"] = str(e)
        return {"context": context}
