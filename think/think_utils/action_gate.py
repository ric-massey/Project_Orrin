from registry.behavior_registry import BEHAVIORAL_FUNCTIONS 
import random 
from datetime import datetime, timezone
from cognition.behavior import extract_last_reflection_topic
from behavior.behavior_generation import generate_behavior_from_integration
from memory.working_memory import update_working_memory
from behavior.speak import OrrinSpeaker
from utils.json_utils import save_json, load_json
from utils.log import log_private, log_model_issue, log_activity
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reward_signals.fatigue import update_function_fatigue, fatigue_penalty_from_context
from paths import GOALS_FILE

MAX_RETRIES = 3

def reflect_on_last_action(context, action, result):
    from utils.generate_response import generate_response
    prompt = (
        f"I executed the action: {action}\n"
        f"The result was:\n{str(result)[:1000]}\n"
        "Reflect: Was it successful? Should I retry, escalate, or ask the user? Reply with either 'success', 'retry', or 'ask th user', and include a brief reason. "
        "If escalation is needed, include the question I should ask the user."
    )
    reflection = generate_response(prompt)
    log_private(f"Reflection: {reflection}")
    return reflection

def generate_clarification_question(context, action):
    from utils.generate_response import generate_response
    prompt = (
        f"I tried to execute the following action, but failed:\n{action}\n"
        "What is the single most important question I should ask the user to get unstuck? Reply only with the question."
    )
    return generate_response(prompt)

def evaluate_and_act_if_needed(context, emotional_state, long_memory, speaker: OrrinSpeaker):
    """
    Evaluates whether Orrin should act now instead of thinking more.
    Mimics the basal ganglia: selects and releases an action if motivation > threshold.
    Executes all pending actions before generating new ones.
    """
    context.setdefault("pending_actions", [])

    # --- Upgrade: limit retries on failed actions ---
    if context["pending_actions"]:
        action = context["pending_actions"].pop(0)
        retries = action.get("retries", 0)
        success = take_action(action, context, speaker)
        reflection = reflect_on_last_action(context, action, success)

        # Escalate if needed
        if isinstance(reflection, str) and "ask the user" in reflection.lower():
            question = generate_clarification_question(context, action)
            if question:
                context["pending_actions"].insert(0, {
                    "type": "ask_user",
                    "content": question,
                    "urgency": 0.99,
                    "description": "Clarification requested for failed action."
                })
        elif isinstance(reflection, str) and "retry" in reflection.lower():
            if retries < MAX_RETRIES:
                action["retries"] = retries + 1
                context["pending_actions"].insert(0, action)
            else:
                # After too many retries, escalate automatically
                question = generate_clarification_question(context, action)
                context["pending_actions"].insert(0, {
                    "type": "ask_user",
                    "content": question or "I'm stuck after multiple retries.",
                    "urgency": 0.99,
                    "description": "Automatic escalation after failed retries."
                })
        return {"action": action}

    context["last_reflection_topic"] = extract_last_reflection_topic()

    possible_actions = generate_behavior_from_integration(context)
    if not possible_actions:
        return False  # No actions generated

    filtered_actions = []
    for action in possible_actions:
        action_type = action.get("type")
        if action_type in BEHAVIORAL_FUNCTIONS and BEHAVIORAL_FUNCTIONS[action_type]["is_action"]:
            filtered_actions.append(action)
    if not filtered_actions:
        return False

    scored = [
        (action, score_action(action, emotional_state, long_memory))
        for action in filtered_actions
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    if len(scored) > 1:
        context["pending_actions"].extend([a for a, _ in scored[1:]])

    best_action, best_score = scored[0]

    if best_score >= 0.75:
        # --- Upgrade: always reset retries on new best action ---
        best_action["retries"] = 0
        success = take_action(best_action, context, speaker)
        reflection = reflect_on_last_action(context, best_action, success)
        if isinstance(reflection, str) and "ask the user" in reflection.lower():
            question = generate_clarification_question(context, best_action)
            if question:
                context["pending_actions"].insert(0, {
                    "type": "ask_user",
                    "content": question,
                    "urgency": 0.99,
                    "description": "Clarification requested for failed action."
                })
        elif isinstance(reflection, str) and "retry" in reflection.lower():
            best_action["retries"] = 1
            context["pending_actions"].insert(0, best_action)
        if success:
            update_function_fatigue(context, best_action["type"])
            motivation = emotional_state.get("motivation", 0.5)
            fatigue = emotional_state.get("fatigue", 0.0)
            actual_reward = 0.6 * (1 - fatigue) * (0.5 + motivation)
            release_reward_signal(context, "dopamine", actual_reward, 0.5, 0.5, source="action_gate")
            context["last_action_taken"] = best_action
            log_activity({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_type": best_action.get("type"),
                "description": best_action.get("description", ""),
                "parameters": {k: v for k, v in best_action.items() if k != "description"},
                "result": "success"
            })
            # --- Upgrade: mark goal completed if action has 'goal_name' field ---
            if "goal_name" in best_action:
                try:
                    from cognition.planning.goals import mark_goal_completed
                    mark_goal_completed(best_action["goal_name"])
                except Exception as e:
                    log_model_issue(f"Could not auto-complete goal from action: {e}")
            return {"action": best_action}
        else:
            log_model_issue("⚠️ Action was selected but failed during execution.")

    return False

def score_action(action, emotional_state, long_memory):
    base = action.get("urgency", 0.5)
    drive = emotional_state.get("drive", 0.0)
    novelty = emotional_state.get("novelty", 0.0)
    motivation = emotional_state.get("motivation", 0.5)
    fatigue = emotional_state.get("fatigue", 0.0)

    fatigue_pen = fatigue_penalty_from_context(emotional_state, action.get("type"))
    
    emotion_bonus = drive + novelty + (0.2 * motivation)
    score = base + emotion_bonus + fatigue_pen

    if action.get("type") == "user_response":
        score += 0.2
    score += random.gauss(0, 0.05)

    return max(0.0, min(1.0, score))

def take_action(action, context, speaker: OrrinSpeaker):
    action_type = action.get("type")
    content = action.get("content", "")
    data = action.get("data")
    path = action.get("path")
    description = action.get("description", action_type)
    log_parameters = {k: v for k, v in action.items() if k != "description"}
    timestamp = datetime.now(timezone.utc).isoformat()

    importance = 2
    if isinstance(action, dict) and "importance" in action:
        importance = action["importance"]
    elif isinstance(content, dict) and "importance" in content:
        importance = content["importance"]
    priority = max(1, int(importance / 2))

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
        if action_type in BEHAVIORAL_FUNCTIONS:
            func = BEHAVIORAL_FUNCTIONS[action_type]["function"]
            result = func(action, context, speaker)
            if result:
                update_function_fatigue(context, action_type)
                release_reward_signal(
                    context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.5, source=f"action:{action_type}"
                )
                update_working_memory({
                    "content": f"Executed action: {description}",
                    "event_type": "action",
                    "action_type": action_type,
                    "parameters": log_parameters,
                    "importance": importance,
                    "priority": priority,
                })
                log_result("success")
            else:
                release_reward_signal(
                    context, "dopamine", 0.2, 0.5, 0.7, source=f"action_fail:{action_type}"
                )
                log_result("fail")
            return result

        if action_type == "speak":
            speaker.speak(content)
            update_function_fatigue(context, "speak")
            release_reward_signal(context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.4, source="action:speak")
            update_working_memory({
                "content": f'Spoke: "{content}"',
                "event_type": "action",
                "action_type": "speak",
                "importance": importance,
                "priority": priority
            })
            log_result("success")
            return True

        elif action_type == "log":
            log_private(content)
            update_function_fatigue(context, "log")
            release_reward_signal(context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.3, source="action:log")
            update_working_memory({
                "content": f"Logged: {content}",
                "event_type": "action",
                "action_type": "log",
                "importance": importance,
                "priority": priority
            })
            log_result("success")
            return True

        elif action_type == "update_file" and path and data:
            save_json(path, data)
            update_function_fatigue(context, "update_file")
            release_reward_signal(context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.6, source="action:update_file")
            update_working_memory({
                "content": f"Updated file: {path}",
                "event_type": "action",
                "action_type": "update_file",
                "parameters": {"path": path},
                "importance": importance,
                "priority": priority
            })
            log_result("success")
            return True

        elif action_type == "set_goal":
            # --- Upgrade: always reload to avoid concurrent overwrite, dedupe, enrich metadata ---
            goals = load_json(GOALS_FILE, default_type=list)
            goal_data = content if isinstance(content, dict) else {"name": str(content)}
            goal_data.setdefault("tier", "short_term")
            goal_data.setdefault("status", "pending")
            goal_data.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            goal_data.setdefault("last_updated", goal_data["timestamp"])
            goal_data.setdefault("emotional_intensity", 0.5)
            goal_data.setdefault("history", [{"event": "created", "timestamp": goal_data["timestamp"]}])
            if not any(g.get("name") == goal_data.get("name") for g in goals):
                goals.append(goal_data)
                save_json(GOALS_FILE, goals)
                context["goals"] = goals
                update_function_fatigue(context, "set_goal")
                release_reward_signal(context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.5, source="action:set_goal")
                goal_text = goal_data.get("goal") if isinstance(goal_data, dict) else str(goal_data)
                update_working_memory({
                    "content": f"Set goal: {goal_text}",
                    "event_type": "action",
                    "action_type": "set_goal",
                    "importance": importance,
                    "priority": priority
                })
                log_result("success")
                return True
            else:
                log_private(f"Goal '{goal_data.get('name')}' already exists. Skipping duplicate.")

        elif action_type == "user_response":
            speaker.speak(content)
            context["last_user_response"] = content
            update_function_fatigue(context, "user_response")
            release_reward_signal(context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.4, source="action:user_response")
            update_working_memory({
                "content": f'User response: "{content}"',
                "event_type": "action",
                "action_type": "user_response",
                "importance": importance,
                "priority": priority
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