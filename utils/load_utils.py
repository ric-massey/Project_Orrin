import json
import os

from utils.json_utils import load_json
from utils.log import (
    log_error, 
    log_model_issue
)
from paths import (
    CONTEXT, MODEL_CONFIG_FILE
)


def load_model_config():
    try:
        if os.path.exists(MODEL_CONFIG_FILE):
            with open(MODEL_CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        log_model_issue(f"[load_model_config] Failed to load model config: {e}")
    
    # fallback defaults
    return {
        "thinking": "gpt-4.1",
        "human_facing": "gpt-4.1"
    }

def load_context():
    return load_json(CONTEXT, default_type=dict)

def load_all_known_json(data_dir="."):
    known = {}

    # Map of expected file base names to their default types
    expected_types = {
        "activity_log": list,
        "context": dict,
        "core_memory": str,
        "cognition_history": list,
        "cognition_schedule": dict,
        "contradictions": list,
        "cycle_count": dict,
        "emotion_model": dict,
        "error_log": str,
        "feedback_log": list,
        "last_active": str,
        "log": str,
        "long_memory": list,
        "model_config": dict,
        "model_failure": str,
        "next_actions": dict,
        "private_thoughts": str,
        "proposed_tools": dict,
        "ref_prompts": dict,
        "relationships": dict,
        "self_model": dict,
        "tool_requests": list,
        "working_memory": list,
        "world_model": dict,
        "casual_rules": list,
        "mode": dict
    }

    for filename in os.listdir(data_dir):
        if filename.endswith(".json"):
            try:
                path = os.path.join(data_dir, filename)
                key = filename.replace(".json", "")
                default_type = expected_types.get(key, dict)  # Default guess: dict
                known[key] = load_json(path, default_type=default_type)
            except Exception as e:
                log_error(f"⚠️ Failed to load {filename}: {e}")

    return known
