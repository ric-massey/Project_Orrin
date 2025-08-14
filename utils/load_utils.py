# utils/load_utils.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Union

from utils.json_utils import load_json
from utils.log import log_error, log_model_issue
from paths import DATA_DIR, CONTEXT, MODEL_CONFIG_FILE


def load_model_config() -> Dict[str, Any]:
    """
    Load the model config; fall back to minimal defaults if unavailable.
    """
    try:
        if MODEL_CONFIG_FILE.exists():
            cfg = load_json(MODEL_CONFIG_FILE, default_type=dict)
            if isinstance(cfg, dict) and cfg:
                return cfg
    except Exception as e:
        log_model_issue(f"[load_model_config] Failed to load model config: {e}")

    # Fallback defaults
    return {
        "thinking": "gpt-4.1",
        "human_facing": "gpt-4.1",
    }


def load_context() -> Dict[str, Any]:
    return load_json(CONTEXT, default_type=dict)


def load_all_known_json(base: Union[Path, str, None] = None) -> Dict[str, Any]:
    """
    Load all *.json files from `base` (defaults to DATA_DIR) and return them in a dict keyed by stem.
    No list is ever passed to Path.glob/rglob.
    """
    base_path = Path(base) if base is not None else DATA_DIR

    if not base_path.exists():
        log_error(f"⚠️ Data directory does not exist: {base_path}")
        return {}

    # Map of expected file base names to their default types
    expected_types: Dict[str, type] = {
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
        "mode": dict,
    }

    out: Dict[str, Any] = {}

    # Only ever pass a string pattern to glob
    for file_path in base_path.glob("*.json"):
        try:
            key = file_path.stem
            default_type = expected_types.get(key, dict)
            out[key] = load_json(file_path, default_type=default_type)
        except Exception as e:
            log_model_issue(f"[load_all_known_json] Failed to load {file_path}: {e}")

    return out
