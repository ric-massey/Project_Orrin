from datetime import datetime, timezone
from utils.json_utils import load_json, save_json, extract_json
from utils.self_model import get_self_model, save_self_model
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_model_issue
from memory.working_memory import update_working_memory
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    FEEDBACK_LOG, LONG_MEMORY_FILE, LOG_FILE,
    PRIVATE_THOUGHTS_FILE,  ACTION_FILE
)

def update_motivations():
    """
    Reflects on recent thoughts and core values to revise Orrin's motivations.
    Updates SELF_MODEL_FILE and logs outcome.
    """
    try:
        self_model = get_self_model()
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)

        recent = [m.get("content") for m in long_memory[-15:] if "content" in m]
        core_values = self_model.get("core_values", [])
        current_motivations = self_model.get("motivations", [])

        context = (
            "Recent reflections:\n" + "\n".join(f"- {r}" for r in recent) + "\n\n"
            "Current motivations:\n" + "\n".join(f"- {m}" for m in current_motivations) + "\n\n"
            "Core values:\n" +
            "\n".join(f"- {v['value']}" if isinstance(v, dict) and "value" in v else f"- {v}" for v in core_values)
        )

        prompt = (
            f"{context}\n\n"
            "Reflect and revise:\n"
            "- Remove misaligned motivations\n"
            "- Add any new ones inspired by recent reflections or values\n"
            "Return JSON ONLY in this format:\n"
            "{\n"
            "  \"updated_motivations\": [\"...\", \"...\"],\n"
            "  \"reasoning\": \"...\"\n"
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        result = extract_json(response)

        if not result or "updated_motivations" not in result:
            raise ValueError("Missing `updated_motivations` in result.")

        self_model["motivations"] = result["updated_motivations"]
        save_self_model(self_model)

        update_working_memory("🧭 Motivations updated: " + ", ".join(result["updated_motivations"]))
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Orrin revised motivations:\n{result['reasoning']}\n")

    except Exception as e:
        log_model_issue(f"[update_motivations] Motivation update failed: {e}")
        update_working_memory("⚠️ Failed to update Orrin's motivations.")

def adjust_priority(goal, fb):
    result_text = fb["result"].lower()
    emotion = fb.get("emotion", "neutral")
    goal["priority"] = goal.get("priority", 5)

    reward = 0.0
    if any(w in result_text for w in ["success", "helpful", "insightful", "effective"]):
        if emotion in ["joy", "excited", "grateful"]:
            goal["priority"] = min(10, goal["priority"] + 2)
            reward = 1.0
        elif emotion in ["satisfied", "curious"]:
            goal["priority"] = min(10, goal["priority"] + 1)
            reward = 0.8

    elif any(w in result_text for w in ["fail", "unhelpful", "repetitive", "useless"]):
        if emotion in ["frustrated", "angry", "ashamed"]:
            goal["priority"] = max(1, goal["priority"] - 2)
            reward = 0.3
        elif emotion in ["bored", "disappointed"]:
            goal["priority"] = max(1, goal["priority"] - 1)
            reward = 0.4

    release_reward_signal(
        {},  # No context in this scope; pass if needed
        signal_type="dopamine",
        actual_reward=reward,
        expected_reward=0.7,
        effort=goal.get("effort", 0.5),
        mode="phasic",
        source="adjusted priority"
    )

def adjust_goal_weights(context=None):
    feedback = load_json(FEEDBACK_LOG, default_type=list)
    next_actions = load_json(ACTION_FILE, default_type=dict)
    trajectory_log = load_json("goal_trajectory_log.json", default_type=dict)
    now = datetime.now(timezone.utc).isoformat()

    if not feedback:
        return

    recent_feedback = feedback[-10:]

    # Flatten next_actions for more robust handling
    all_goals = []
    if isinstance(next_actions, dict):
        for tier in ["short_term", "mid_term", "long_term"]:
            all_goals.extend(next_actions.get(tier, []))
    elif isinstance(next_actions, list):
        all_goals = next_actions

    for goal in all_goals:
        name = goal.get("name")
        if not name:
            continue
        for fb in recent_feedback:
            if fb["goal"] == name:
                adjust_priority(goal, fb)
        trajectory_log.setdefault(name, []).append({
            "timestamp": now,
            "priority": goal["priority"],
            "tier": goal.get("tier", "unknown")
        })

    save_json(ACTION_FILE, next_actions)
    save_json("goal_trajectory_log.json", trajectory_log)

    with open(LOG_FILE, "a") as f:
        f.write(f"\n[{now}] Orrin adjusted goal priorities and released reward signals based on feedback.\n")