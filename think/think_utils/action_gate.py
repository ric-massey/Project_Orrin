from cognition.behavior import generate_behavior_from_integration
from cognition.speak import OrrinSpeaker
from utils.json_utils import save_json
from utils.log import log_private, log_model_issue
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import GOALS_FILE

def evaluate_and_act_if_needed(context, emotional_state, long_memory, speaker: OrrinSpeaker):
    """
    Evaluates whether Orrin should act now instead of thinking more.
    Mimics the basal ganglia: selects and releases an action if motivation > threshold.
    """
    possible_actions = generate_behavior_from_integration(context)
    if not possible_actions:
        return False  # No actions generated

    # Score all possible actions
    scored = [
        (action, score_action(action, emotional_state, long_memory))
        for action in possible_actions
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_action, best_score = scored[0]

    # === Threshold check ===
    if best_score >= 0.75:
        speaker.speak(f"I feel compelled to act: {best_action['description']}")
        success = take_action(best_action, context, speaker)

        if success:
            release_reward_signal(context, "dopamine", 0.6, 0.5, 0.5, source="action_gate")
            context["last_action_taken"] = best_action
            return {"action": best_action}
        else:
            log_model_issue("⚠️ Action was selected but failed during execution.")

    return False

def score_action(action, emotional_state, long_memory):
    """
    Returns a score for the action based on urgency, emotion, and possible relevance.
    """
    base = action.get("urgency", 0.5)
    drive = emotional_state.get("drive", 0.0)
    novelty = emotional_state.get("novelty", 0.0)
    emotion_bonus = drive + novelty

    if action.get("type") == "user_response":
        base += 0.2  # Prioritize responsiveness

    return min(1.0, base + emotion_bonus)

def take_action(action, context, speaker: OrrinSpeaker):
    """
    Executes a real-world action. This is Orrin's motor cortex.
    """
    action_type = action.get("type")
    content = action.get("content", "")
    data = action.get("data")
    path = action.get("path")
    description = action.get("description", action_type)

    try:
        if action_type == "speak":
            speaker.speak(content)
            return True

        elif action_type == "log":
            log_private(content)
            return True

        elif action_type == "update_file" and path and data:
            save_json(path, data)
            return True

        elif action_type == "set_goal":
            goals = context.get("goals", [])
            goals.append(content)
            save_json(GOALS_FILE, goals)
            context["goals"] = goals
            return True

        elif action_type == "user_response":
            speaker.speak(content)
            context["last_user_response"] = content
            return True

        else:
            log_model_issue(f"⚠️ Unknown action type: {action_type}")
            return False

    except Exception as e:
        log_private(f"❌ take_action failed: {e}")
        return False