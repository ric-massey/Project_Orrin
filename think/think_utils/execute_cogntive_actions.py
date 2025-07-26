# === Imports ===
from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.log import log_private, log_model_issue
from memory.working_memory import update_working_memory
from paths import GOALS_FILE, LONG_MEMORY_FILE
from utils.emotion_utils import detect_emotion
from utils.self_model import get_self_model, save_self_model
from emotion.reward_signals.reward_signals import release_reward_signal


def execute_cognitive_action(action_dict, context=None):
    """
    Handles cognitive-level actions that do not trigger behavioral output.
    These include modifying goals, internal beliefs, or the self-model.
    """
    if not isinstance(action_dict, dict):
        log_model_issue("❌ execute_cognitive_action() received non-dict input.")
        return

    action_type = action_dict.get("action", "").lower()
    timestamp = datetime.now(timezone.utc).isoformat()

    # === 1. Add Goal ===
    if action_type == "add_goal":
        goal = action_dict.get("goal")
        if isinstance(goal, dict):
            goals = load_json(GOALS_FILE, default_type=list)
            goal.setdefault("timestamp", timestamp)
            goal.setdefault("origin", "cognitive_action")
            goals.append(goal)
            save_json(GOALS_FILE, goals)

            update_working_memory({
                "content": f"🧠 New goal added: {goal.get('description')}",
                "event_type": "add_goal",
                "importance": 2,
                "priority": 2,
                "referenced": 1
            })
            log_private(f"[execute_cognitive_action] Added goal: {goal}")

            # Reward for adding goal
            if context:
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.6,
                    expected_reward=0.4,
                    effort=0.5,
                    source="add_goal"
                )
        else:
            log_model_issue("⚠️ Invalid goal format in add_goal action.")

    # === 2. Update Belief ===
    elif action_type == "update_belief":
        belief = action_dict.get("belief")
        if isinstance(belief, str):
            memory = load_json(LONG_MEMORY_FILE, default_type=list)
            memory.append({
                "content": f"Belief updated: {belief}",
                "timestamp": timestamp,
                "emotion": detect_emotion(belief),
                "event_type": "update_belief",
            })
            save_json(LONG_MEMORY_FILE, memory)

            update_working_memory({
                "content": f"🧠 Updated belief: {belief}",
                "event_type": "update_belief",
                "importance": 2,
                "priority": 1,
                "referenced": 1
            })
            log_private(f"[execute_cognitive_action] Updated belief: {belief}")

            # Reward for updating belief
            if context:
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.5,
                    expected_reward=0.4,
                    effort=0.6,
                    source="update_belief"
                )
        else:
            log_model_issue("⚠️ Invalid belief format in update_belief action.")

    # === 3. Revise Self Model ===
    elif action_type == "revise_self_model":
        patch = action_dict.get("patch")
        if isinstance(patch, dict):
            model = get_self_model()
            model.update(patch)
            save_self_model(model)

            update_working_memory({
                "content": "🧠 Self-model revised.",
                "event_type": "revise_self_model",
                "importance": 2,
                "priority": 2,
                "referenced": 1
            })
            log_private(f"[execute_cognitive_action] Self-model updated with patch: {patch}")

            # Reward for revising self-model (high effort)
            if context:
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.7,
                    expected_reward=0.5,
                    effort=0.8,
                    source="revise_self_model"
                )
        else:
            log_model_issue("⚠️ Invalid patch format in revise_self_model action.")

    # === 4. Log Thought ===
    elif action_type == "log_thought":
        content = action_dict.get("content")
        if content:
            memory = load_json(LONG_MEMORY_FILE, default_type=list)
            memory.append({
                "content": content,
                "timestamp": timestamp,
                "emotion": detect_emotion(content),
                "event_type": "log_thought"
            })
            save_json(LONG_MEMORY_FILE, memory)

            update_working_memory({
                "content": f"🧠 Thought logged: {content}",
                "event_type": "log_thought",
                "importance": 1,
                "priority": 1,
                "referenced": 0
            })
            log_private(f"[execute_cognitive_action] Thought logged to long-term memory.")

            # Small reward for logging thought
            if context:
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.3,
                    expected_reward=0.4,
                    effort=0.2,
                    source="log_thought"
                )
        else:
            log_model_issue("⚠️ No content provided for log_thought.")

    # === Unknown Action ===
    else:
        log_model_issue(f"❓ Unknown cognitive action type: {action_type}")