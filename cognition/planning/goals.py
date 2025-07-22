import json
import os
from datetime import datetime, timezone
from typing import List, Dict
from utils.load_utils import load_json
from utils.memory_utils import summarize_memories
from utils.summarizers import summarize_self_model
from utils.generate_response import generate_response
from utils.self_model import get_self_model
from memory.working_memory import update_working_memory
from utils.json_utils import extract_json 

from paths import GOALS_FILE, COMPLETED_GOALS_FILE, FOCUS_GOAL, LONG_MEMORY_FILE

MAX_GOALS = 15

# === Load and Save ===
def load_goals() -> List[Dict]:
    try:
        with open(GOALS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_goals(goals: List[Dict]):
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)

# === Pruning Logic ===
def prune_goals(goals: List[Dict]) -> List[Dict]:
    status_priority = {"pending": 0, "in_progress": 1, "completed": 2, "abandoned": 3}

    active_goals = []
    completed_goals = []

    for g in goals:
        status = g.get("status", "pending")
        if status in ["completed", "abandoned"]:
            completed_goals.append(g)
        else:
            active_goals.append(g)

    if completed_goals:
        try:
            if os.path.exists(COMPLETED_GOALS_FILE):
                with open(COMPLETED_GOALS_FILE, "r") as f:
                    existing = json.load(f)
            else:
                existing = []
        except:
            existing = []

        existing.extend(completed_goals)

        with open(COMPLETED_GOALS_FILE, "w") as f:
            json.dump(existing, f, indent=2)

    active_goals.sort(key=lambda g: (
        status_priority.get(g.get("status", "pending"), 4),
        g.get("tier_score", 3),
        -g.get("emotional_intensity", 0),
        g.get("last_updated", g.get("timestamp", ""))
    ))

    return active_goals[:MAX_GOALS]

# === Focus Goal Selection ===
def select_focus_goals(goals: List[Dict]) -> Dict[str, Dict]:
    focus = {"short_or_mid": None, "long_term": None}

    for goal in goals:
        if goal["status"] in ["pending", "in_progress", "active"]:
            if goal["tier"] in ["short_term", "mid_term"] and not focus["short_or_mid"]:
                focus["short_or_mid"] = goal
            elif goal["tier"] == "long_term" and not focus["long_term"]:
                focus["long_term"] = goal
        if focus["short_or_mid"] and focus["long_term"]:
            break

    with open(FOCUS_GOAL, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "short_or_mid": focus["short_or_mid"],
            "long_term": focus["long_term"]
        }, f, indent=2)

    return focus

# === Ensure Long-Term Anchor ===
DEFAULT_LONG_TERM_NAME = "Understand self and user"

def ensure_long_term_goal(goals: List[Dict]) -> List[Dict]:
    active_exists = any(
        g.get("tier") == "long_term" and g.get("status") in ["pending", "in_progress"]
        for g in goals
    )
    if active_exists:
        return goals

    try:
        if os.path.exists(COMPLETED_GOALS_FILE):
            with open(COMPLETED_GOALS_FILE, "r") as f:
                completed = json.load(f)
        else:
            completed = []
    except Exception:
        completed = []

    has_ever_had_long_term = any(
        g.get("tier") == "long_term"
        for g in goals + completed
    )

    if has_ever_had_long_term:
        return goals

    now = datetime.now(timezone.utc).isoformat()
    new_goal = {
        "name": DEFAULT_LONG_TERM_NAME,
        "tier": "long_term",
        "tier_score": 3,
        "description": "Continually deepen understanding of both Orrin's identity and the user’s needs and growth.",
        "status": "pending",
        "timestamp": now,
        "completed_timestamp": None,
        "emotional_intensity": 0.8,
        "estimated_difficulty": 5,
        "expected_cycles": 10,
        "last_updated": now,
        "history": [{"event": "created", "timestamp": now}]
    }

    goals.append(new_goal)
    return goals

# === Main Goal Processing Pipeline ===
def update_and_select_focus_goals() -> Dict[str, Dict]:
    goals = load_goals()
    goals = ensure_long_term_goal(goals)
    goals = prune_goals(goals)
    save_goals(goals)
    return select_focus_goals(goals)

def mark_goal_completed(goal_name):
    goals = load_json(GOALS_FILE, default_type=list)
    updated = False
    for goal in goals:
        if goal.get("name") == goal_name and goal.get("status") not in ["completed", "abandoned"]:
            goal["status"] = "completed"
            now_iso = datetime.now(timezone.utc).isoformat()
            goal["completed_timestamp"] = now_iso
            goal["last_updated"] = now_iso
            goal.setdefault("history", []).append({"event": "completed", "timestamp": now_iso})
            updated = True
    if updated:
        save_goals(goals)
        update_and_select_focus_goals() 
        print(f"✅ Marked goal '{goal_name}' as completed.")
    return updated

def maybe_complete_goals():
    goals = load_json(GOALS_FILE, default_type=list)
    for goal in goals:
        if goal.get("status") not in ["completed", "abandoned"]:
            check_prompt = (
                f"Goal: {goal.get('name')} — {goal.get('description')}\n"
                "Based on my recent memories, working memory, and self-model below, is this goal completed?\n"
                "Respond ONLY with JSON: {\"completed\": true/false, \"why\": \"...\"}\n"
                "If unsure, respond with {\"completed\": false, \"why\": \"Insufficient data\"}.\n\n"
                f"Recent memories: {summarize_memories(load_json(LONG_MEMORY_FILE, default_type=list)[-10:])}\n"
                f"Self-model summary: {summarize_self_model(get_self_model())}\n"
            )
            result = generate_response(check_prompt)
            check = extract_json(result)
            if isinstance(check, dict) and check.get("completed", False):
                mark_goal_completed(goal.get("name"))
                update_working_memory(f"🎉 Completed goal: {goal.get('name')} ({check.get('why', '')})")
            else:
                update_working_memory(f"⚠️ Could not parse or goal not complete for '{goal.get('name')}': {result}")