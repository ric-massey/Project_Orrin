from utils.json_utils import save_json, load_json
from memory.working_memory import update_working_memory
from paths import EMOTIONAL_STATE_FILE

def apply_emotional_feedback(cognition_name, score):
    emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict)
    core = emotional_state.get("core_emotions", {})

    if score >= 0.5:
        core["happiness"] = core.get("happiness", 0) + score
    elif score <= -0.5:
        core["frustration"] = core.get("frustration", 0) + abs(score)
    elif abs(score) < 0.2:
        core["confusion"] = core.get("confusion", 0) + 0.1

    emotional_state["core_emotions"] = core
    save_json(EMOTIONAL_STATE_FILE, emotional_state)
    update_working_memory(f"Emotional feedback applied: score={score} affected state.")