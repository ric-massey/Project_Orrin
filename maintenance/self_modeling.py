# === Imports ===
from datetime import datetime, timezone
import json
from utils.json_utils import (
    load_json,
    extract_json
)
from utils.self_model import get_self_model, save_self_model
from utils.log import log_model_issue, log_private
from paths import (
    FEEDBACK_LOG, LONG_MEMORY_FILE
)
from utils.generate_response import generate_response, get_thinking_model

# === Function ===
def prune_old_threads():
    self_model = get_self_model()
    if not isinstance(self_model, dict):
        return "❌ Invalid self model. Expected a dictionary."

    config = self_model.get("config", {})
    if not isinstance(config, dict):
        config = {}

    max_age_days = config.get("max_thread_age_days", 14)
    max_threads = config.get("max_imaginative_threads", 10)

    imaginative_threads = self_model.get("imaginative_threads", [])
    if not isinstance(imaginative_threads, list):
        imaginative_threads = []

    now = datetime.now(timezone.utc)
    kept = []

    for thread in imaginative_threads:
        if not isinstance(thread, dict):
            continue
        try:
            timestamp = datetime.fromisoformat(thread.get("timestamp", ""))
            age = (now - timestamp).days
            if age <= max_age_days:
                kept.append(thread)
        except Exception:
            continue

    kept = kept[-max_threads:]
    removed_count = len(imaginative_threads) - len(kept)
    self_model["imaginative_threads"] = kept
    save_self_model(self_model)

    if removed_count > 0:
        log_private(f"Orrin pruned {removed_count} old imaginative threads.")

def update_influence_scores_from_feedback():
    feedback = load_json(FEEDBACK_LOG, default_type=list)
    self_model = get_self_model()
    agents = self_model.get("internal_agents", [])
    success = [f for f in feedback if "success" in f.get("result", "").lower()]

    for entry in success:
        agent_name = entry.get("agent", "")
        for agent in agents:
            if agent.get("name") == agent_name:
                agent["influence_score"] = min(agent.get("influence_score", 0.5) + 0.05, 1.0)

    self_model["internal_agents"] = agents
    save_self_model(self_model)

def self_model_maintenance_cycle():
    prune_old_threads()
    update_influence_scores_from_feedback()
    # ✅ Add more maintenance routines here if needed

def self_supervised_repair():
    self_model = get_self_model()
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(self_model, dict) or not isinstance(long_memory, list):
        return

    recent = [m.get("content") for m in long_memory[-12:] if isinstance(m, dict) and "content" in m]

    prompt = (
        "I am a self-reflective AI.\n"
        "Compare the following recent thoughts against my current self_model.\n"
        "Look for internal contradictions, emotional tensions, or value misalignments.\n"
        "If contradictions exist, try to:\n"
        "- Add or revise `biases`, `stances`, or `recent_changes`\n"
        "- Flag conflicting `core_beliefs`\n"
        "- Gently revise `identity_story` if it no longer fits\n\n"
        "Recent thoughts:\n"
        + "\n".join(f"- {t}" for t in recent)
        + "\n\nCurrent self_model:\n"
        + json.dumps(self_model, indent=2)
        + "\n\nRespond ONLY with an updated self_model JSON reflecting these contradictions and my internal attempt to repair them."
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    if response:
        try:
            updated = extract_json(response)
            if isinstance(updated, dict):
                save_self_model(updated)
                log_private("Self-supervised contradiction repair occurred.")
        except Exception as e:
            log_model_issue(f"[self_supervised_repair] JSON parse error: {e}\nRaw: {response}")