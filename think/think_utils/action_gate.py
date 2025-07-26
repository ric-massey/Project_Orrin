from registry.behavior_registry import BEHAVIORAL_FUNCTIONS 
import random 
from datetime import datetime, timezone
from cognition.behavior import extract_last_reflection_topic
from behavior.behavior_generation import generate_behavior_from_integration
from memory.working_memory import update_working_memory
from behavior.speak import OrrinSpeaker
from utils.json_utils import save_json
from utils.log import log_private, log_model_issue, log_activity
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reward_signals.fatigue import update_function_fatigue, fatigue_penalty_from_context
from paths import GOALS_FILE

def evaluate_and_act_if_needed(context, emotional_state, long_memory, speaker: OrrinSpeaker):
    """
    Evaluates whether Orrin should act now instead of thinking more.
    Mimics the basal ganglia: selects and releases an action if motivation > threshold.
    """
    # --- Always inject latest reflection topic before behavior generation ---
    context["last_reflection_topic"] = extract_last_reflection_topic()

    # Generate all possible actions using integration
    possible_actions = generate_behavior_from_integration(context)
    if not possible_actions:
        return False  # No actions generated

    # === Filter for actual behavioral actions only (if your function doesn't already) ===
    filtered_actions = []
    for action in possible_actions:
        # Each action should have a 'type' that matches a behavioral function name
        action_type = action.get("type")
        if action_type in BEHAVIORAL_FUNCTIONS and BEHAVIORAL_FUNCTIONS[action_type]["is_action"]:
            filtered_actions.append(action)
    if not filtered_actions:
        return False

    # Score all filtered possible actions
    scored = [
        (action, score_action(action, emotional_state, long_memory))
        for action in filtered_actions
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_action, best_score = scored[0]

    # === Threshold check ===
    if best_score >= 0.75:
        success = take_action(best_action, context, speaker)

        if success:
            # Update fatigue tracking for this action
            update_function_fatigue(context, best_action["type"])

            # Modulate reward based on motivation and fatigue
            motivation = emotional_state.get("motivation", 0.5)
            fatigue = emotional_state.get("fatigue", 0.0)
            actual_reward = 0.6 * (1 - fatigue) * (0.5 + motivation)  # example modulation

            release_reward_signal(context, "dopamine", actual_reward, 0.5, 0.5, source="action_gate")
            context["last_action_taken"] = best_action

            # === Add this: ===
            log_activity({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": best_action.get("type"),
            "description": best_action.get("description", ""),
            "parameters": {k: v for k, v in best_action.items() if k != "description"},
            "result": "success"
        })
        # =================
            return {"action": best_action}
        else:
            log_model_issue("⚠️ Action was selected but failed during execution.")

    return False

def score_action(action, emotional_state, long_memory):
    """
    Returns a score for the action based on urgency, emotion, motivation, fatigue, and relevance.
    """
    base = action.get("urgency", 0.5)
    drive = emotional_state.get("drive", 0.0)
    novelty = emotional_state.get("novelty", 0.0)
    motivation = emotional_state.get("motivation", 0.5)
    fatigue = emotional_state.get("fatigue", 0.0)

    # Incorporate fatigue penalty if tracked
    fatigue_pen = fatigue_penalty_from_context(emotional_state, action.get("type"))
    
    emotion_bonus = drive + novelty + (0.2 * motivation)
    score = base + emotion_bonus + fatigue_pen

    # Prioritize user_response type slightly
    if action.get("type") == "user_response":
        score += 0.2

    # Add small noise to simulate variability
    score += random.gauss(0, 0.05)

    return max(0.0, min(1.0, score))

from datetime import datetime, timezone

def take_action(action, context, speaker: OrrinSpeaker):
    """
    Executes a real-world action. This is Orrin's motor cortex.
    Logs every action attempt to both working memory and log_activity.json.
    Integrates reward signals and fatigue updates for each action execution.
    """
    action_type = action.get("type")
    content = action.get("content", "")
    data = action.get("data")
    path = action.get("path")
    description = action.get("description", action_type)
    log_parameters = {k: v for k, v in action.items() if k != "description"}
    timestamp = datetime.now(timezone.utc).isoformat()

    def log_result(result="success", error=None):
        entry = {
            "timestamp": timestamp,
            "action_type": action_type,
            "description": description,
            "parameters": log_parameters,
            "result": result
        }
        if error:
            entry["error"] = str(error)
        log_activity(entry)

    try:
        # Use the behavioral registry to execute the right function if available
        if action_type in BEHAVIORAL_FUNCTIONS:
            func = BEHAVIORAL_FUNCTIONS[action_type]["function"]
            result = func(action, context, speaker)
            if result:
                update_function_fatigue(context, action_type)
                release_reward_signal(
                    context, "dopamine", 0.6, 0.5, 0.5, source=f"action:{action_type}"
                )
                update_working_memory({
                    "content": f"Executed action: {description}",
                    "event_type": "action",
                    "action_type": action_type,
                    "parameters": log_parameters,
                    "importance": 2,
                    "priority": 2,
                })
                log_result("success")
            else:
                release_reward_signal(
                    context, "dopamine", 0.2, 0.5, 0.7, source=f"action_fail:{action_type}"
                )
                log_result("fail")
            return result

        # Default behaviors (fallbacks if no registry entry)
        if action_type == "speak":
            speaker.speak(content)
            update_function_fatigue(context, "speak")
            release_reward_signal(context, "dopamine", 0.5, 0.5, 0.4, source="action:speak")
            update_working_memory({
                "content": f'Spoke: "{content}"',
                "event_type": "action",
                "action_type": "speak",
                "importance": 2,
                "priority": 2
            })
            log_result("success")
            return True

        elif action_type == "log":
            log_private(content)
            update_function_fatigue(context, "log")
            release_reward_signal(context, "dopamine", 0.4, 0.5, 0.3, source="action:log")
            update_working_memory({
                "content": f"Logged: {content}",
                "event_type": "action",
                "action_type": "log",
                "importance": 1,
                "priority": 1
            })
            log_result("success")
            return True

        elif action_type == "update_file" and path and data:
            save_json(path, data)
            update_function_fatigue(context, "update_file")
            release_reward_signal(context, "dopamine", 0.6, 0.5, 0.6, source="action:update_file")
            update_working_memory({
                "content": f"Updated file: {path}",
                "event_type": "action",
                "action_type": "update_file",
                "parameters": {"path": path},
                "importance": 2,
                "priority": 2
            })
            log_result("success")
            return True

        elif action_type == "set_goal":
            goals = context.get("goals", [])
            goals.append(content)
            save_json(GOALS_FILE, goals)
            context["goals"] = goals
            update_function_fatigue(context, "set_goal")
            release_reward_signal(context, "dopamine", 0.7, 0.5, 0.5, source="action:set_goal")
            update_working_memory({
                "content": f"Set goal: {content}",
                "event_type": "action",
                "action_type": "set_goal",
                "importance": 2,
                "priority": 2
            })
            log_result("success")
            return True

        elif action_type == "user_response":
            speaker.speak(content)
            context["last_user_response"] = content
            update_function_fatigue(context, "user_response")
            release_reward_signal(context, "dopamine", 0.6, 0.5, 0.4, source="action:user_response")
            update_working_memory({
                "content": f'User response: "{content}"',
                "event_type": "action",
                "action_type": "user_response",
                "importance": 2,
                "priority": 2
            })
            log_result("success")
            return True

        else:
            log_model_issue(f"⚠️ Unknown action type: {action_type}")
            update_working_memory({
                "content": f"⚠️ Unknown action type attempted: {action_type}",
                "event_type": "action_fail",
                "action_type": action_type,
                "importance": 1,
                "priority": 1
            })
            release_reward_signal(context, "dopamine", 0.1, 0.5, 0.7, source="action_fail:unknown")
            log_result("fail")
            return False

    except Exception as e:
        log_private(f"❌ take_action failed: {e}")
        update_working_memory({
            "content": f"⚠️ Failed to execute action: {description} — {e}",
            "event_type": "action_fail",
            "action_type": action_type,
            "importance": 1,
            "priority": 1
        })
        release_reward_signal(context, "dopamine", 0.1, 0.5, 0.8, source="action_fail:exception")
        log_result("exception", error=e)
        return False