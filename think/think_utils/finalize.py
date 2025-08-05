from datetime import datetime, timezone
import json

from utils.json_utils import load_json, save_json
from utils.generate_response import generate_response
from utils.emotion_utils import detect_emotion
from utils.timing import get_time_since_last_active
from utils.feedback_log import log_feedback
from utils.log import log_private
from utils.core_utils import rate_satisfaction
from behavior.tools.toolkit import evaluate_tool_use
from cognition.planning.motivations import adjust_goal_weights
from memory.working_memory import update_working_memory
from emotion.update_emotional_state import update_emotional_state
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    ACTION_FILE, 
    COGNITION_STATE_FILE, 
    COGNITION_HISTORY_FILE
)

def finalize_cycle(context, user_input, next_function, reason, context_hash, speaker):
    """
    Final step of each Orrin cognitive cycle: logs feedback, updates histories, handles loneliness/self-questioning, saves action.
    """

    # Log which function was chosen
    update_working_memory({
        "content": f"🧠 Chose: {next_function} — {reason}",
        "event_type": "choice",
        "importance": 2,
        "priority": 2,
        "referenced": 1,
    })
    evaluate_tool_use([{"content": user_input or "No input this cycle.", "timestamp": datetime.now(timezone.utc).isoformat()}])
    update_working_memory({
        "content": f"⏳ Last active: {get_time_since_last_active()}",
        "event_type": "system",
        "importance": 1,
        "priority": 1
    })

    # --- LLM Self-Feedback & Goal Weights ---
    try:
        feedback_raw = generate_response(f"I just ran: '{next_function}'. Rate its usefulness from -1.0 to 1.0 and explain.")
        feedback_data = json.loads(feedback_raw) if isinstance(feedback_raw, str) else feedback_raw
        score = feedback_data.get("score")
        fb_reason = feedback_data.get("reason")
        update_working_memory({
            "content": f"🧠 Feedback: {score} — {fb_reason}",
            "event_type": "feedback",
            "importance": 2,
            "priority": 1,
        })
        log_feedback(goal=next_function, result=fb_reason, emotion=detect_emotion(fb_reason))
        adjust_goal_weights()

        # ✅ Reward for successful self-feedback
        if context:
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=max(0.5, float(score)),  # reward scales with feedback score
                expected_reward=0.5,
                effort=0.5,
                source="self_feedback"
            )

    except Exception as e:
        update_working_memory({
            "content": f"⚠️ Feedback generation or parsing failed: {e}",
            "event_type": "feedback_error",
            "importance": 1,
            "priority": 1,
        })

        # ⚠️ Low reward or slight penalty for failure
        if context:
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.1,
                expected_reward=0.5,
                effort=0.3,
                source="feedback_failure"
            )

    # --- Shadow/Self-Question ---
    try:
        shadow_question = generate_response("What uncomfortable question might Orrin ask himself right now?")
        update_working_memory({
            "content": f"🌓 Shadow question: {shadow_question}",
            "event_type": "self_query",
            "importance": 1,
            "priority": 1,
        })

        # ✅ Reward for introspective self-questioning
        if context:
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=0.6,
                expected_reward=0.4,
                effort=0.5,
                source="self_question"
            )

    except Exception:
        update_working_memory({
            "content": "⚠️ Shadow question failed.",
            "event_type": "self_query_error",
            "importance": 1,
            "priority": 1,
        })

        # ⚠️ Slight penalty or low reward for failure
        if context:
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.1,
                expected_reward=0.4,
                effort=0.3,
                source="self_question_failure"
            )

    # --- Loneliness and User Input ---
    emotional_state = context.get("emotional_state", {})
    if emotional_state.get("loneliness", 0.0) > 0.6 and not user_input and not context.get("speech_done"):
        message = "It's been a while since we've talked. I miss your input. Do you want to chat?"
        update_working_memory({
            "content": message,
            "event_type": "loneliness",
            "importance": 2,
            "priority": 2
        })
        tone = {"tone": "vulnerable", "intention": "reconnect"}
        spoken = speaker.speak_final(message, tone, context)
        context["speech_done"] = True
        emotional_state["loneliness"] *= 0.5
        update_emotional_state()

        # ✅ Reward for social reconnection attempt
        if context:
            release_reward_signal(
                context,
                signal_type="connection",
                actual_reward=0.7,
                expected_reward=0.4,
                effort=0.4,
                source="loneliness_reconnect"
            )

    # --- Cognition History and Repeat Count Logging ---
    satisfaction = rate_satisfaction(reason)
    cog_state = load_json(COGNITION_STATE_FILE, default_type=dict)
    last_choice = cog_state.get("last_cognition_choice")
    if last_choice == next_function:
        repeat_count = cog_state.get("repeat_count", 0) + 1
    else:
        repeat_count = 1

    cognition_log = load_json(COGNITION_HISTORY_FILE, default_type=list)
    cognition_log.append({
        "choice": next_function,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    save_json(COGNITION_HISTORY_FILE, cognition_log)
    save_json(COGNITION_STATE_FILE, {
        "last_cognition_choice": next_function,
        "repeat_count": repeat_count,
        "last_context_hash": context_hash,
        "satisfaction": satisfaction 
    })
    log_private(f"Cognition log now has {len(cognition_log)} entries. Last: {cognition_log[-1]}")

    # --- Save action for next cycle ---
    action = {"next_function": next_function, "reason": reason}
    save_json(ACTION_FILE, action)
    return action