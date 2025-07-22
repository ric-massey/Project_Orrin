from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import EMOTIONAL_STATE_FILE, LAST_TAGS, REWARD_TRACE

def log_feedback(goal, result, emotion="neutral", agent="Orrin", score=None, file="data/feedback_log.json"):
    entry = {
        "goal": goal,
        "result": result,
        "agent": agent,
        "emotion": emotion,
        "timestamp": str(datetime.now(timezone.utc))
    }

    if score is not None:
        entry["score"] = score

    log = load_json(file, default_type=list)
    log.append(entry)
    save_json(file, log)

    # === Simulate reward ===
    context = {
        EMOTIONAL_STATE_FILE: load_json(EMOTIONAL_STATE_FILE, default_type=dict),
        REWARD_TRACE: load_json("data/reward_trace.json", default_type=list),
        LAST_TAGS: [goal, agent]
    }

    # Set reward signal type based on result/emotion
    actual_reward = float(score or 0.0)
    expected_reward = 0.6  # you could adjust this dynamically later
    effort = 0.5  # you could estimate this based on how hard Orrin worked for the goal

    if result.lower() in ["success", "helpful", "insightful", "effective"]:
        context = release_reward_signal(context, signal_type="dopamine", actual_reward=actual_reward, expected_reward=expected_reward, effort=effort, mode="phasic")
    elif result.lower() in ["failure", "unhelpful", "useless"]:
        context = release_reward_signal(context, signal_type="dopamine", actual_reward=actual_reward, expected_reward=expected_reward, effort=effort, mode="phasic")
    else:
        context = release_reward_signal(context, signal_type="serotonin", actual_reward=0.5, expected_reward=expected_reward, effort=effort)

    save_json(EMOTIONAL_STATE_FILE, context[EMOTIONAL_STATE_FILE])
    save_json("data/reward_trace.json", context[REWARD_TRACE])