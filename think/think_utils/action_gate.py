import random
import json
from datetime import datetime, timezone
import time  # NEW
from pathlib import Path  # NEW

from think.think_utils.escalate import escalate_with_behavior_list
from cognition.behavior import extract_last_reflection_topic
from behavior.behavior_generation import generate_behavior_from_integration
from behavior.speak import OrrinSpeaker
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reward_signals.fatigue import update_function_fatigue, fatigue_penalty_from_context
from memory.working_memory import update_working_memory
from registry.behavior_registry import BEHAVIORAL_FUNCTIONS
from utils.json_utils import save_json, load_json
from utils.log import log_private, log_model_issue, log_activity
from utils.emotion_utils import log_pain
from paths import GOALS_FILE, FOCUS_GOAL

MAX_RETRIES = 3
AGENTIC_TYPES = {
    "write_file",
    "execute_python_code",
    "run_tool",
    "scrape_text",
    "web_search",
    "update_file",
}

REFLECTIONY = {"reflect", "plan", "summarize", "analyz", "deliberat", "log", "think"}


def _novelty_for(action_type: str, context: dict, *, forced: bool = False) -> float:
    """
    Lightweight novelty heuristic so upstream can log/learn from variety.
    """
    prev = (context.get("last_action_taken") or {}).get("type")
    base = 0.15
    agentic_bump = 0.2 if action_type in AGENTIC_TYPES else 0.05
    diff = 0.2 if prev and prev != action_type else 0.0
    forced_bonus = 0.25 if forced else 0.0
    return max(0.0, min(1.0, base + agentic_bump + diff + forced_bonus))


def _stamp_outcome(ctx: dict, outcome: dict) -> None:
    """
    Store per-cycle telemetry fields used by finalize/logging.
    Safe no-op on any errors.
    """
    try:
        act = outcome.get("action") or {}
        ctx["last_result"] = {
            "source": outcome.get("source"),
            "action_type": act.get("type"),
            "success": bool(outcome.get("success", False)),
        }
        ctx["last_novelty"] = float(outcome.get("novelty") or 0.0)
        ctx.setdefault("last_acceptance_pass", False)
    except Exception:
        pass


def reflect_on_last_action(context, action, result):
    from utils.generate_response import generate_response
    prompt = (
        f"I executed the action: {action}\n"
        f"The result was:\n{str(result)[:1000]}\n"
        "Reflect: Was it successful? Should I retry, escalate, or ask the user? "
        "Reply with either 'success', 'retry', or 'ask the user', and include a brief reason. "
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


def moving_average(lst, n):
    if not lst or n <= 0:
        return 3
    return sum(lst[-n:]) / min(n, len(lst))


def _cycles(context):
    raw = context.get("cycle_count", 0)
    return raw.get("count", 0) if isinstance(raw, dict) else int(raw or 0)


def update_adaptive_context(context, action_type=None):
    context.setdefault("action_history", [])
    context.setdefault("cycles_since_agentic_action", 0)
    context.setdefault("prev_cycles_since_action", 0)
    context.setdefault("frustration", 0.0)

    context.setdefault("committed_goal", None)
    context.setdefault("action_debt", 0)
    context.setdefault("act_now", False)

    now_cycle = _cycles(context)
    if action_type:
        context["action_history"].append(
            {"cycle": now_cycle, "action_type": action_type, "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    agentic_times = [a for a in context["action_history"] if a["action_type"] in AGENTIC_TYPES]
    if len(agentic_times) > 1:
        diffs = [agentic_times[i]["cycle"] - agentic_times[i - 1]["cycle"] for i in range(1, len(agentic_times))]
        avg_gap = moving_average(diffs, 10)
    else:
        avg_gap = 3

    dynamic_max_cycles = max(2, int(avg_gap * 1.2))

    debt = int(context.get("action_debt", 0) or 0)
    if context.get("act_now"):
        dynamic_max_cycles = max(1, int(dynamic_max_cycles * 0.6))
    if debt >= 2:
        dynamic_max_cycles = max(1, dynamic_max_cycles - min(debt, 3))

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
    context.setdefault("committed_goal", None)
    context.setdefault("action_debt", 0)
    context.setdefault("act_now", False)
    context.setdefault("minimum_viable_action", None)

    dynamic_max_cycles, derivative = update_adaptive_context(context)
    cur = context.get("cycles_since_agentic_action", 0)
    frustration = context.get("frustration", 0.0)

    # ✅ pull current focus goal name once per call
    focus_name = _current_focus_name() or ""

    if context.get("act_now") and isinstance(context.get("minimum_viable_action"), dict):
        mv = context["minimum_viable_action"]
        mv_type = mv.get("type")
        if mv_type in BEHAVIORAL_FUNCTIONS:
            log_activity(f"🧭 Act-now: executing minimum viable action: {mv_type}")
            ok = take_action(mv, context, speaker)
            update_adaptive_context(context, mv_type)
            if ok:
                context["minimum_viable_action"] = None
                context["cycles_since_agentic_action"] = 0
                context["frustration"] = max(0, context["frustration"] - 0.2)
                # NEW: mark that we acted this tick
                context["last_action_ts"] = time.time()
                context["__acted_this_tick__"] = True

                outcome = {
                    "action": mv,
                    "success": True,
                    "novelty": _novelty_for(mv_type, context),
                    "acted": True,
                    "source": "act_now",
                }
                _stamp_outcome(context, outcome)
                return outcome

    if context["pending_actions"]:
        action = context["pending_actions"].pop(0)
        retries = action.get("retries", 0)
        success = take_action(action, context, speaker)
        update_adaptive_context(context, action.get("type"))
        reflection = reflect_on_last_action(context, action, success)

        text = (reflection or "").lower()
        if "ask the user" in text:
            question = generate_clarification_question(context, action)
            if question:
                context["pending_actions"].insert(0, {
                    "type": "ask_user",
                    "content": question,
                    "urgency": 0.99,
                    "description": "Clarification requested for failed action.",
                })
        elif "retry" in text:
            if retries < MAX_RETRIES:
                action["retries"] = retries + 1
                context["pending_actions"].insert(0, action)
            else:
                return escalate_with_behavior_list(
                    context=context,
                    action=action,
                    last_error=context.get("last_error", ""),
                    retries=retries,
                )
        outcome = {
            "action": action,
            "success": bool(success),
            "novelty": _novelty_for(action.get("type", ""), context),
            "acted": True,
            "source": "pending",
        }
        # NEW: only stamp as acted if the pending action succeeded
        if success:
            context["last_action_ts"] = time.time()
            context["__acted_this_tick__"] = True

        _stamp_outcome(context, outcome)
        return outcome

    context["last_reflection_topic"] = extract_last_reflection_topic()

    # NEW: consume cached proposals if present (e.g., produced in dreams_emotional_logic)
    possible_actions = context.pop("behavior_proposals", None)
    if not possible_actions:
        possible_actions = generate_behavior_from_integration(context)
    if not possible_actions:
        return False

    # NEW: allow select fallback types even if not in registry
    filtered_actions = []
    FALLBACK_TYPES = {"ask_user", "write_file", "execute_python_code"}
    for action in possible_actions:
        action_type = action.get("type")
        meta = BEHAVIORAL_FUNCTIONS.get(action_type)
        if (meta and meta.get("is_action")) or (action_type in FALLBACK_TYPES):
            filtered_actions.append(action)
    if not filtered_actions:
        return False

    def score_action(action, emotional_state, long_memory):
        base = action.get("urgency", 0.5)
        drive = emotional_state.get("drive", 0.0)
        novelty = emotional_state.get("novelty", 0.0)
        motivation = emotional_state.get("motivation", 0.5)

        fatigue_pen = fatigue_penalty_from_context(emotional_state, action.get("type"))
        stagnation_boost = 0.11 * context.get("cycles_since_agentic_action", 0) if action.get("type") in AGENTIC_TYPES else 0
        derivative_boost = 0.09 * derivative if action.get("type") in AGENTIC_TYPES and derivative > 0 else 0

        is_reflectiony = any(key in (action.get("type","").lower()) for key in REFLECTIONY)
        frustration_penalty = -0.25 * frustration if is_reflectiony else 0.0
        act_now_bonus = 0.0
        if context.get("act_now"):
            if action.get("type") in AGENTIC_TYPES:
                act_now_bonus += 0.18
            if is_reflectiony:
                act_now_bonus -= 0.22

        # ✅ Focus alignment bonus
        focus_bonus = 0.0
        if focus_name:
            if action.get("goal_name") == focus_name:
                focus_bonus += 0.25
            else:
                desc = (action.get("description") or "").lower()
                cont = action.get("content")
                if not isinstance(cont, str):
                    try:
                        cont = json.dumps(cont, default=str)
                    except Exception:
                        cont = ""
                if focus_name.lower() in desc or focus_name.lower() in (cont or "").lower():
                    focus_bonus += 0.15

        emotion_bonus = drive + novelty + (0.2 * motivation)
        score = (
            base + emotion_bonus - fatigue_pen +
            stagnation_boost + derivative_boost +
            frustration_penalty + act_now_bonus +
            focus_bonus
        )
        if action.get("type") == "user_response":
            score += 0.2
        score += random.gauss(0, 0.05)
        return max(0.0, min(1.0, score))

    scored = [(action, score_action(action, emotional_state, long_memory)) for action in filtered_actions]
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
        best_agentic, _ = max(((a, score_action(a, emotional_state, long_memory)) for a in agentic_actions), key=lambda x: x[1])
        novelty_reward = 0.4 + 0.05 * cur
        take_action(best_agentic, context, speaker)
        # NEW: treat forced agentic as acted
        context["last_action_ts"] = time.time()
        context["__acted_this_tick__"] = True

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
            "result": "forced",
        })
        context["frustration"] = max(0, context["frustration"] - 0.2)
        outcome = {
            "action": best_agentic,
            "success": True,
            "novelty": max(0.0, min(1.0, 0.4 + 0.05 * cur)),
            "acted": True,
            "source": "forced_agentic",
        }
        _stamp_outcome(context, outcome)
        return outcome

    if cur >= dynamic_max_cycles and not agentic_actions:
        log_private("⚠️ Frustration maxed, but no agentic action available—defaulting to random action.")
        log_pain(context, "frustration", increment=0.5 + 0.05 * cur)
        action, _ = random.choice(scored)
        take_action(action, context, speaker)
        # NEW: treat forced random as acted
        context["last_action_ts"] = time.time()
        context["__acted_this_tick__"] = True

        update_working_memory({
            "content": f"Random action due to stagnation: {action['type']}",
            "event_type": "forced_action",
            "importance": 1,
            "priority": 1,
        })
        outcome = {
            "action": action,
            "success": True,  # treat as taken; if you want real success, capture take_action() return
            "novelty": _novelty_for(action.get("type", ""), context, forced=True),
            "acted": True,
            "source": "forced_random",
        }
        _stamp_outcome(context, outcome)
        return outcome

    best_action, best_score = scored[0]

    if best_action["type"] in AGENTIC_TYPES:
        context["cycles_since_agentic_action"] = 0
    else:
        context["cycles_since_agentic_action"] += 1
    update_adaptive_context(context, best_action["type"])

    if best_score >= 0.75:
        best_action["retries"] = 0
        success = take_action(best_action, context, speaker)
        reflection = reflect_on_last_action(context, best_action, success)

        text = (reflection or "").lower()
        if "ask the user" in text:
            question = generate_clarification_question(context, best_action)
            if question:
                context["pending_actions"].insert(0, {
                    "type": "ask_user",
                    "content": question,
                    "urgency": 0.99,
                    "description": "Clarification requested for failed action.",
                })
        elif "retry" in text:
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
                "result": "success",
            })
            update_working_memory({
                "content": f"Executed: {best_action['type']} - {best_action.get('description', '')}",
                "event_type": "action",
                "importance": 2,
                "priority": 2,
            })
            if "goal_name" in best_action:
                try:
                    from cognition.planning.goals import mark_goal_completed
                    mark_goal_completed(best_action["goal_name"])
                except Exception as e:
                    log_model_issue(f"Could not auto-complete goal from action: {e}")
            context["frustration"] = max(0, context["frustration"] - 0.2)

            # NEW: mark that we acted this tick
            context["last_action_ts"] = time.time()
            context["__acted_this_tick__"] = True

            outcome = {
                "action": best_action,
                "success": True,
                "novelty": _novelty_for(best_action.get("type", ""), context),
                "acted": True,
                "source": "scored_best",
            }
            _stamp_outcome(context, outcome)
            return outcome
        else:
            log_model_issue("⚠️ Action was selected but failed during execution.")
            outcome = {
                "action": best_action,
                "success": False,
                "novelty": 0.05,
                "acted": True,
                "source": "scored_best",
            }
            _stamp_outcome(context, outcome)
            return outcome

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
            "result": result,
        }
        if error:
            entry["error"] = str(error)
        log_activity(entry)

    try:
        meta = BEHAVIORAL_FUNCTIONS.get(action_type)
        if meta:
            func = meta.get("function")
            result = func(action, context, speaker)
            if result:
                update_function_fatigue(context, action_type)
                release_reward_signal(context, "dopamine", 0.3 + 0.05 * importance, 0.5, 0.5, source=f"action:{action_type}")
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
                release_reward_signal(context, "dopamine", 0.2, 0.5, 0.7, source=f"action_fail:{action_type}")
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
                "priority": priority,
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
                "priority": priority,
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
                "priority": priority,
            })
            log_result("success")
            return True

        elif action_type == "set_goal":
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
                    "priority": priority,
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
                "priority": priority,
            })
            log_result("success")
            return True

        # -------- NEW FALLBACKS (non-registry) --------
        elif action_type == "ask_user":
            speaker.speak(content)
            update_function_fatigue(context, "ask_user")
            release_reward_signal(context, "dopamine", 0.32 + 0.05 * importance, 0.5, 0.4, source="action:ask_user")
            update_working_memory({
                "content": f'Question to user: "{content}"',
                "event_type": "action",
                "action_type": "ask_user",
                "importance": importance,
                "priority": priority,
            })
            log_result("success")
            return True

        elif action_type == "write_file":
            file_path = Path(action.get("path") or "")
            text = action.get("text", "")
            append = bool(action.get("append", False))
            only_if_missing = action.get("only_if_missing")
            if not file_path:
                log_model_issue("write_file missing 'path'")
                log_result("fail")
                return False
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if only_if_missing and file_path.exists():
                    try:
                        existing = file_path.read_text(encoding="utf-8")
                        if str(only_if_missing) in existing:
                            log_private(f"⏩ Skipped write_file; marker already present in {file_path}")
                            log_result("success")
                            return True
                    except Exception:
                        pass
                mode = "a" if append else "w"
                with file_path.open(mode, encoding="utf-8") as f:
                    f.write(text)
                update_function_fatigue(context, "write_file")
                release_reward_signal(context, "dopamine", 0.35 + 0.05 * importance, 0.5, 0.5, source="action:write_file")
                update_working_memory({
                    "content": f"Wrote to file: {str(file_path)}",
                    "event_type": "action",
                    "action_type": "write_file",
                    "parameters": {"path": str(file_path)},
                    "importance": importance,
                    "priority": priority,
                })
                log_result("success")
                return True
            except Exception as e:
                log_private(f"write_file failed: {e}")
                log_result("exception", error=e)
                return False

        elif action_type == "execute_python_code":
            code = action.get("code", "")
            if not isinstance(code, str) or not code.strip():
                log_model_issue("execute_python_code missing 'code'")
                log_result("fail")
                return False
            try:
                _globals = {}
                _locals = {}
                exec(code, _globals, _locals)
                update_function_fatigue(context, "execute_python_code")
                release_reward_signal(context, "dopamine", 0.36 + 0.05 * importance, 0.5, 0.6, source="action:execute_python_code")
                update_working_memory({
                    "content": f"Executed python code: {code[:160]}{'...' if len(code) > 160 else ''}",
                    "event_type": "action",
                    "action_type": "execute_python_code",
                    "importance": importance,
                    "priority": priority,
                })
                log_result("success")
                return True
            except Exception as e:
                log_private(f"execute_python_code failed: {e}")
                log_result("exception", error=e)
                return False
        # ------------------------------------------------

        else:
            log_model_issue(f"⚠️ Unknown action type: {action_type}")
            update_working_memory({
                "content": f"⚠️ Unknown action type attempted: {action_type}",
                "event_type": "action_fail",
                "action_type": action_type,
                "importance": 1,
                "priority": 1,
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
            "priority": 1,
        })
        release_reward_signal(context, "dopamine", 0.1, 0.5, 0.8, source="action_fail:exception")
        log_result("exception", error=e)
        return False


def _current_focus_name():
    try:
        data = load_json(FOCUS_GOAL)
        if isinstance(data, dict):
            from utils.goals import extract_current_focus_goal
            return extract_current_focus_goal(data)
    except Exception:
        pass
    return None
