from datetime import datetime, timezone
import json

from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response
from emotion.emotion import detect_emotion  # fixed import
from utils.timing import get_time_since_last_active
from utils.feedback_log import log_feedback
from utils.log import log_private, log_model_issue
from utils.core_utils import rate_satisfaction
from utils.events import emit_event, DECISION
from behavior.tools.toolkit import evaluate_tool_use
from cognition.planning.motivations import adjust_goal_weights
from memory.working_memory import update_working_memory
from emotion.update_emotional_state import update_emotional_state
from emotion.reward_signals.reward_signals import release_reward_signal
from utils.bandit import record_outcome_ctx
from think.think_utils.escalate import is_agentic_action
from utils.context_key import context_key
from paths import (
    ACTION_FILE,
    COGNITION_STATE_FILE,
    COGNITION_HISTORY_FILE,
    BEHAVIORAL_FUNCTIONS_LIST_FILE,  # use the real constant
)

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# NEW: ensure we can display and score 'reason' whether it's a dict or a string
def _reason_text(reason) -> str:
    if isinstance(reason, dict):
        try:
            return json.dumps(reason, ensure_ascii=False)
        except Exception:
            return str(reason)
    return str(reason)

def _reward(context, *, signal, actual, expected, effort, mode, source):
    if not context:
        return
    try:
        release_reward_signal(
            context=context,
            signal_type=signal,
            actual_reward=float(actual),
            expected_reward=float(expected),
            effort=float(effort),
            mode=mode,
            source=source,
        )
    except Exception as e:
        log_model_issue(f"reward signal failed ({source}): {e}")

def finalize_cycle(context, user_input, next_function, reason, context_hash, speaker):
    """
    Final step of each Orrin cognitive cycle: logs feedback, updates histories,
    handles loneliness/self-questioning, and saves the chosen action.
    """
    reason_text = _reason_text(reason)  # NEW

    # Log which function was chosen
    update_working_memory({
        "content": f"🧠 Chose: {next_function} — {reason_text}",  # NEW: use readable text
        "event_type": "choice",
        "importance": 2,
        "priority": 2,
        "referenced": 1
    })
    evaluate_tool_use([{
        "content": user_input or "No input this cycle.",
        "timestamp": _utc_now()
    }])
    update_working_memory({
        "content": f"⏳ Last active: {get_time_since_last_active()}",
        "event_type": "system",
        "importance": 1,
        "priority": 1
    })

    # --- Agentic-vs-Cognition Reward System ---
    is_agentic = is_agentic_action(next_function, behavior_list_path=BEHAVIORAL_FUNCTIONS_LIST_FILE)
    if is_agentic:
        _reward(context, signal="dopamine", actual=1.0, expected=0.6, effort=0.7, mode="phasic", source="agentic_action")
        update_working_memory({
            "content": f"✅ Rewarded agentic action: {next_function}",
            "event_type": "reward",
            "importance": 2,
            "priority": 2
        })
    else:
        _reward(context, signal="dopamine", actual=0.2, expected=0.4, effort=0.2, mode="tonic", source="cognition_only")
        update_working_memory({
            "content": f"⚠️ Cognition action only (not agentic): {next_function}",
            "event_type": "reward_penalty",
            "importance": 1,
            "priority": 1
        })

    # --- LLM Self-Feedback & Goal Weights ---
    try:
        fb_raw = generate_response(
            f"I just ran: '{next_function}'. Rate its usefulness from -1.0 to 1.0 and explain.\n"
            'Respond as JSON: {"score": <float>, "reason": "<short explanation>"}'
        )
        fb = extract_json(fb_raw) if isinstance(fb_raw, str) else (fb_raw or {})
        if not isinstance(fb, dict):
            fb = {}
        score = float(fb.get("score", 0.0))
        fb_reason = str(fb.get("reason", "")).strip() or "No reason given."
        update_working_memory({
            "content": f"🧠 Feedback: {score} — {fb_reason}",
            "event_type": "feedback",
            "importance": 2,
            "priority": 1
        })
        log_feedback(goal=next_function, result=fb_reason, emotion=detect_emotion(fb_reason))
        adjust_goal_weights()

        _reward(context, signal="dopamine", actual=max(0.5, score), expected=0.5, effort=0.5, mode="phasic", source="self_feedback")
    except Exception as e:
        update_working_memory({
            "content": f"⚠️ Feedback generation or parsing failed: {e}",
            "event_type": "feedback_error",
            "importance": 1,
            "priority": 1
        })
        _reward(context, signal="dopamine", actual=0.1, expected=0.5, effort=0.3, mode="phasic", source="feedback_failure")

    # --- Shadow/Self-Question ---
    try:
        shadow_question = generate_response("What uncomfortable question might Orrin ask himself right now?")
        update_working_memory({
            "content": f"🌓 Shadow question: {shadow_question or ''}",
            "event_type": "self_query",
            "importance": 1,
            "priority": 1
        })
        _reward(context, signal="novelty", actual=0.6, expected=0.4, effort=0.5, mode="tonic", source="self_question")
    except Exception:
        update_working_memory({
            "content": "⚠️ Shadow question failed.",
            "event_type": "self_query_error",
            "importance": 1,
            "priority": 1
        })
        _reward(context, signal="dopamine", actual=0.1, expected=0.4, effort=0.3, mode="phasic", source="self_question_failure")

    # --- Loneliness and User Input ---
    emotional_state = context.get("emotional_state", {}) or {}
    if emotional_state.get("loneliness", 0.0) > 0.6 and not user_input and not context.get("speech_done"):
        message = "It's been a while since we've talked. I miss your input. Do you want to chat?"
        update_working_memory({
            "content": message,
            "event_type": "loneliness",
            "importance": 2,
            "priority": 2
        })
        tone = {"tone": "vulnerable", "intention": "reconnect"}
        speaker.speak_final(message, tone, context)
        context["speech_done"] = True
        emotional_state["loneliness"] = emotional_state.get("loneliness", 0.0) * 0.5
        # pass context so state updates in-place consistently
        update_emotional_state(context=context)

        _reward(context, signal="connection", actual=0.7, expected=0.4, effort=0.4, mode="tonic", source="loneliness_reconnect")

    # --- Cognition History and Repeat Count Logging ---
    satisfaction = rate_satisfaction(reason_text)  # NEW: always a string
    cog_state = load_json(COGNITION_STATE_FILE, default_type=dict) or {}
    last_choice = cog_state.get("last_cognition_choice")
    repeat_count = (cog_state.get("repeat_count", 0) + 1) if last_choice == next_function else 1

    cognition_log = load_json(COGNITION_HISTORY_FILE, default_type=list)
    if not isinstance(cognition_log, list):
        cognition_log = []
    cognition_log.append({
        "choice": next_function,
        "reason": reason,  # keep raw (dict or string) for fidelity
        "timestamp": _utc_now()
    })
    save_json(COGNITION_HISTORY_FILE, cognition_log)

    # 🧭 recent_picks tracking (feeds novelty/boredom in select_function)
    try:
        rp = context.get("recent_picks", [])
        if not isinstance(rp, list):
            rp = []
        rp.append(next_function)
        context["recent_picks"] = rp[-50:]  # keep a small rolling window
    except Exception:
        pass

    save_json(COGNITION_STATE_FILE, {
        "last_cognition_choice": next_function,
        "repeat_count": repeat_count,
        "last_context_hash": context_hash,
        "satisfaction": satisfaction,
        "recent_picks": context.get("recent_picks", []),  # <-- persisted for transparency
    })
    log_private(f"Cognition log now has {len(cognition_log)} entries. Last: {cognition_log[-1]}")

    # === Outcome-driven Brain: Per-tick decision record ===
    try:
        tick = (context.get("cycle_count") or {}).get("count", 0)
        goal_ctx = context.get("committed_goal") or context.get("focus_goal")
        event_payload = {
            "tick": tick,
            "goal_ctx": goal_ctx,
            "decision": {
                "picked": next_function,
                "reason": reason,  # keep raw
                "candidates": context.get("last_candidates", []),
                "is_action": bool(is_agentic),
            },
            "tools_used": context.get("last_tools", []),
            "result": context.get("last_result", {}),
            "reward": {
                "dopamine": float(context.get("last_reward", 0.0)),
                "novelty": float(context.get("last_novelty", 0.0)),
                "acceptance_passed": bool(context.get("last_acceptance_pass", False)),
            },
            "followups": context.get("pending_actions", []),
        }
        emit_event(DECISION, event_payload)

        # Record contextual bandit outcome from satisfaction + bonuses
        base = rate_satisfaction(reason_text)  # NEW: consistent string
        bonus = 0.0
        if is_agentic:
            bonus += 0.25
        if bool(context.get("last_acceptance_pass", False)):
            bonus += 0.5
        reward_val = max(0.0, min(1.0, float(base + bonus)))
        record_outcome_ctx(context_key(context), next_function, reward_val)
        context["last_reward"] = reward_val
    except Exception as _e:
        log_model_issue(f"Event emit/bandit record failed: {_e}")

    # --- Save action for next cycle ---
    action = {"next_function": next_function, "reason": reason}
    save_json(ACTION_FILE, action)
    return action
