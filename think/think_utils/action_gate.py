import random 
from datetime import datetime, timezone
from cognition.behavior import extract_last_reflection_topic
from behavior.behavior_generation import generate_behavior_from_integration
from memory.working_memory import update_working_memory
from behavior.speak import OrrinSpeaker
from utils.json_utils import save_json, load_json
from utils.log import log_private, log_model_issue, log_activity
from utils.emotion_utils import  log_pain
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reward_signals.fatigue import update_function_fatigue, fatigue_penalty_from_context
from paths import GOALS_FILE
from registry.behavior_registry import BEHAVIORAL_FUNCTIONS 

MAX_RETRIES = 3
AGENTIC_TYPES = {"write_file", "execute_python_code", "run_tool", "scrape_text", "web_search", "update_file"}

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

# --- Adaptive overlays (no breaking I/O) ---
def moving_average(lst, n):
    if not lst or n <= 0:
        return 3
    return sum(lst[-n:]) / min(n, len(lst))

def update_adaptive_context(context, action_type=None):
    context.setdefault("action_history", [])
    context.setdefault("cycles_since_agentic_action", 0)
    context.setdefault("prev_cycles_since_action", 0)
    context.setdefault("frustration", 0.0)
    now_cycle = context.get("cycle_count", 0)
    if action_type:
        context["action_history"].append({
            "cycle": now_cycle,
            "action_type": action_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    agentic_times = [a for a in context["action_history"] if a["action_type"] in AGENTIC_TYPES]
    if len(agentic_times) > 1:
        diffs = [agentic_times[i]["cycle"] - agentic_times[i-1]["cycle"] for i in range(1, len(agentic_times))]
        avg_gap = moving_average(diffs, 10)
    else:
        avg_gap = 3
    dynamic_max_cycles = max(2, int(avg_gap * 1.2))
    prev = context.get("prev_cycles_since_action", 0)
    cur = context.get("cycles_since_agentic_action", 0)
    derivative = cur - prev
    context["prev_cycles_since_action"] = cur
    frustration = context.get("frustration", 0.0)
    if cur > dynamic_max_cycles:
        frustration += 0.13 * (1.4 ** (cur - dynamic_max_cycles))
    else:
        frustration = max(0, frustration - 0.05)
    context["frustration"] = min(frustration, 1.0)
    return dynamic_max_cycles, derivative

def evaluate_and_act_if_needed(context, emotional_state, long_memory, speaker: OrrinSpeaker):
    context.setdefault("pending_actions", [])
    dynamic_max_cycles, derivative = update_adaptive_context(context)
    cur = context.get("cycles_since_agentic_action", 0)
    frustration = context.get("frustration", 0.0)

    # --- Handle pending actions (existing logic preserved) ---
    if context["pending_actions"]:
        action = context["pending_actions"].pop(0)
        retries = action.get("retries", 0)
        success = take_action(action, context, speaker)
        update_adaptive_context(context, action.get("type"))
        reflection = reflect_on_last_action(context, action, success)
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

    def score_action(action, emotional_state, long_memory):
        base = action.get("urgency", 0.5)
        drive = emotional_state.get("drive", 0.0)
        novelty = emotional_state.get("novelty", 0.0)
        motivation = emotional_state.get("motivation", 0.5)
        fatigue = emotional_state.get("fatigue", 0.0)
        fatigue_pen = fatigue_penalty_from_context(emotional_state, action.get("type"))
        stagnation_boost = 0.11 * context.get("cycles_since_agentic_action", 0) if action.get("type") in AGENTIC_TYPES else 0
        derivative_boost = 0.09 * derivative if action.get("type") in AGENTIC_TYPES and derivative > 0 else 0
        frustration_penalty = -0.25 * context.get("frustration", 0.0) if action.get("type") in {"reflect", "speak", "plan", "summarize", "log"} else 0
        emotion_bonus = drive + novelty + (0.2 * motivation)
        score = base + emotion_bonus + fatigue_pen + stagnation_boost + derivative_boost + frustration_penalty
        if action.get("type") == "user_response":
            score += 0.2
        score += random.gauss(0, 0.05)
        return max(0.0, min(1.0, score))

    scored = [
        (action, score_action(action, emotional_state, long_memory))
        for action in filtered_actions
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    if len(scored) > 1:
        context["pending_actions"].extend([a for a, _ in scored[1:]])

    agentic_actions = [a for a in filtered_actions if a["type"] in AGENTIC_TYPES]
    if cur >= dynamic_max_cycles and agentic_actions:
        log_private(f"🚨 Stagnation: Forcing agentic action after {cur} cycles (max {dynamic_max_cycles})")
        from emotion.emotion_learning import update_emotion_function_map
        update_emotion_function_map("frustration", "agentic_action")
        context["boredom_count"] = 0
        context["cycles_since_agentic_action"] = 0
        best_agentic, _ = max(
            ((a, score_action(a, emotional_state, long_memory)) for a in agentic_actions),
            key=lambda x: x[1]
        )
        novelty_reward = 0.4 + 0.05 * cur
        take_action(best_agentic, context, speaker)
        release_reward_signal(context, "dopamine", novelty_reward, 0.6, 0.8, source="forced_agentic_action")
        update_working_memory({
            "content": f"Forcing agentic action: {best_agentic['type']} after {cur} cycles.",
            "event_type": "forced_action",
            "importance": 2,
            "priority": 2,
        })
        log_activity({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": best_agentic.get("type"),
            "description": best_agentic.get("description", ""),
            "parameters": {k: v for k, v in best_agentic.items() if k != "description"},
            "result": "forced"
        })
        context["frustration"] = max(0, context["frustration"] - 0.2)
        return {"action": best_agentic}

    if cur >= dynamic_max_cycles and not agentic_actions:
        log_private("⚠️ Frustration maxed, but no agentic action available—defaulting to random action.")
        log_pain(context, "frustration", increment=0.5 + 0.05 * cur)
        action, _ = random.choice(scored)
        take_action(action, context, speaker)
        update_working_memory({
            "content": f"Random action due to stagnation: {action['type']}",
            "event_type": "forced_action",
            "importance": 1,
            "priority": 1,
        })
        return {"action": action}

    best_action, best_score = scored[0]

    # Track adaptive overlays (does nothing if action type missing)
    if best_action["type"] in AGENTIC_TYPES:
        context["cycles_since_agentic_action"] = 0
    else:
        context["cycles_since_agentic_action"] += 1
    update_adaptive_context(context, best_action["type"])

    if best_score >= 0.75:
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
            actual_reward = 0.6 * (1 - fatigue) * (0.5 + motivation) + 0.18 * context.get("frustration", 0.0)
            release_reward_signal(context, "dopamine", actual_reward, 0.5, 0.5, source="action_gate")
            context["last_action_taken"] = best_action
            log_activity({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_type": best_action.get("type"),
                "description": best_action.get("description", ""),
                "parameters": {k: v for k, v in best_action.items() if k != "description"},
                "result": "success"
            })
            update_working_memory({
                "content": f"Executed: {best_action['type']} - {best_action.get('description', '')}",
                "event_type": "action",
                "importance": 2,
                "priority": 2
            })
            # GOALS_FILE logic is never bypassed
            if "goal_name" in best_action:
                try:
                    from cognition.planning.goals import mark_goal_completed
                    mark_goal_completed(best_action["goal_name"])
                except Exception as e:
                    log_model_issue(f"Could not auto-complete goal from action: {e}")
            context["frustration"] = max(0, context["frustration"] - 0.2)
            return {"action": best_action}
        else:
            log_model_issue("⚠️ Action was selected but failed during execution.")

    return False

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