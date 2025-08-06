import json
import os
from datetime import datetime, timezone
from typing import List, Dict
from utils.load_utils import load_json
from utils.generate_response import generate_response
from memory.working_memory import update_working_memory
from utils.json_utils import extract_json 
from utils.log import log_activity
from emotion.reward_signals.reward_signals import release_reward_signal

from paths import GOALS_FILE, COMPLETED_GOALS_FILE, FOCUS_GOAL

MAX_GOALS = 15

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# === Load and Save, but handle goal tree ===
def load_goals() -> List[Dict]:
    try:
        with open(GOALS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_goals(goals: List[Dict]):
    # Sort by last_updated descending (most recent first)
    goals_sorted = sorted(
        goals,
        key=lambda g: g.get("last_updated", g.get("timestamp", "")),
        reverse=True
    )
    # Limit to 10
    goals_to_save = goals_sorted[:10]
    with open(GOALS_FILE, "w") as f:
        json.dump(goals_to_save, f, indent=2)

# === Prune finished/abandoned goals recursively ===
def prune_goals(goals: List[Dict]) -> List[Dict]:
    def is_active(goal):
        return goal.get("status", "pending") not in ["completed", "abandoned"]

    def prune(goal):
        if "subgoals" in goal:
            goal["subgoals"] = [prune(sub) for sub in goal["subgoals"] if is_active(sub)]
        return goal

    return [prune(g) for g in goals if is_active(g)]

# === Goal Decomposition ===
def decompose_goal(goal: Dict) -> List[Dict]:
    """
    Uses LLM to break down a complex goal into actionable subgoals.
    """
    prompt = (
        f"Decompose the following goal into 3-7 concrete, sequential subgoals.\n"
        f"Goal: {goal.get('name', goal.get('description', 'Unnamed'))}\n"
        f"Be concise. Output JSON list of subgoals: [\"...\", \"...\", ...]"
    )
    result = generate_response(prompt)
    subgoals = extract_json(result)
    # Return as goal dicts
    if isinstance(subgoals, list):
        now = now_iso()
        return [{
            "name": s if isinstance(s, str) else str(s),
            "status": "pending",
            "timestamp": now,
            "last_updated": now,
            "subgoals": [],
            "history": [{"event": "created", "timestamp": now}],
        } for s in subgoals]
    return []

# === Try To Accomplish Goal ===
def try_to_accomplish(goal: Dict) -> bool:
    """
    Plug in your LLM/tool integration for atomic actions.
    Returns True if succeeded, False if needs decomposition.
    """
    # Placeholder logic; replace with your action logic!
    # E.g., call a function, write code, etc.
    prompt = f"Try to accomplish this atomic goal: {goal.get('name', '')}\nDescribe outcome as JSON: {{'success': true/false, 'details': '...'}}"
    result = generate_response(prompt)
    out = extract_json(result)
    if isinstance(out, dict) and out.get("success"):
        goal["status"] = "completed"
        goal["last_updated"] = now_iso()
        goal.setdefault("history", []).append({"event": "completed", "timestamp": now_iso()})
        update_working_memory(f"✅ Accomplished goal: {goal.get('name')}")
        return True
    else:
        goal.setdefault("history", []).append({"event": "failed_attempt", "timestamp": now_iso()})
        return False

# === Recursively Pursue Goal Tree ===
def pursue_goal(goal: Dict):
    # If has subgoals, pursue next uncompleted
    if "subgoals" in goal and goal["subgoals"]:
        for sub in goal["subgoals"]:
            if sub.get("status", "pending"):
                pursue_goal(sub)
                # Only pursue one at a time (depth-first)
                return
        # All subgoals completed: mark this goal complete
        mark_goal_completed(goal)
    else:
        result = try_to_accomplish(goal)
        if not result:
            # If not yet decomposed, try decomposition
            if not goal.get("decomposed"):
                subgoals = decompose_goal(goal)
                if subgoals:
                    goal["subgoals"] = subgoals
                    goal["decomposed"] = True
                    save_goals([goal])  # Or update entire tree as needed
                    update_working_memory(f"🪓 Decomposed goal: {goal.get('name')}")
                    return
            # If already decomposed once but failed, escalate or ask user
            else:
                update_working_memory(f"⚠️ Blocked on goal: {goal.get('name')}. Needs user input or abandonment.")
                # Optionally set status or escalate
                goal["status"] = "blocked"
                goal["last_updated"] = now_iso()

def mark_goal_completed(goal: Dict):
    goal["status"] = "completed"
    goal["completed_timestamp"] = now_iso()
    goal["last_updated"] = now_iso()
    goal.setdefault("history", []).append({"event": "completed", "timestamp": now_iso()})
    release_reward_signal(
        context=None,
        signal_type="dopamine",
        actual_reward=1.0,
        expected_reward=0.7,
        effort=0.4,
        mode="phasic"
    )
    update_working_memory(f"🎉 Completed goal: {goal.get('name')}")
    log_activity(f"✅ Marked goal '{goal.get('name')}' as completed.")

# === Focus Goal Selection remains mostly unchanged, but supports nested goals ===
def select_focus_goals() -> dict:
    """
    Loads goals from GOALS_FILE, selects focus goals, and writes to FOCUS_GOAL.
    Returns the focus goal dictionary.
    """
    goals = load_json(GOALS_FILE, default_type=list)

    def find_focus(goal_list, tier_names, collected, max_count):
        for goal in goal_list:
            if len(collected) >= max_count:
                break
            if goal.get("status") in ["pending", "in_progress", "active"]:
                if goal.get("tier") in tier_names:
                    collected.append(goal)
                if "subgoals" in goal:
                    find_focus(goal["subgoals"], tier_names, collected, max_count)
        return collected

    # Only up to 2 short/mid, 1 long term
    short_or_mid_goals = find_focus(goals, ["short_term", "mid_term"], [], 2)
    long_term_goals = find_focus(goals, ["long_term"], [], 1)

    focus = {
        "short_or_mid": short_or_mid_goals[0] if short_or_mid_goals else None,
        "long_term": long_term_goals[0] if long_term_goals else None,
    }

    with open(FOCUS_GOAL, "w") as f:
        json.dump({
            "timestamp": now_iso(),
            "short_or_mid": focus["short_or_mid"],
            "long_term": focus["long_term"]
        }, f, indent=2)

    return focus

# === Ensure/Anchor long-term goals remains unchanged, but sets as parent ===
DEFAULT_LONG_TERM_NAME = "Understand self and user"

def ensure_long_term_goal(goals: List[Dict]) -> List[Dict]:
    def contains_long_term(goal_list):
        for g in goal_list:
            if g.get("tier") == "long_term" and g.get("status") in ["pending", "in_progress"]:
                return True
            if "subgoals" in g and contains_long_term(g["subgoals"]):
                return True
        return False

    if contains_long_term(goals):
        return goals

    now = now_iso()
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
        "history": [{"event": "created", "timestamp": now}],
        "subgoals": [],
    }
    goals.append(new_goal)
    return goals

# === Main update function, now recursive ===
def update_and_select_focus_goals() -> Dict[str, Dict]:
    goals = load_goals()
    goals = ensure_long_term_goal(goals)
    goals = prune_goals(goals)
    save_goals(goals)
    return select_focus_goals(goals)

# === Utilities for search/uniqueness, etc. unchanged but now may need to recurse tree ===
def goal_function_already_exists(goal_tree, function_name):
    """
    Checks if any goal (recursive) already uses this function name.
    """
    for goal in goal_tree:
        goal_text = goal.get("goal", "") + " " + goal.get("name", "")
        if function_name in goal_text:
            return True
        if "subgoals" in goal:
            if goal_function_already_exists(goal["subgoals"], function_name):
                return True
    return False

# cognition/planning/goals.py

def maybe_complete_goals():
    """
    Traverses the full goal tree.
    - Marks goals as completed if all subgoals are completed.
    - Logs and rewards each completion.
    - Saves updated goals back to GOALS_FILE and, optionally, COMPLETED_GOALS_FILE.
    """
    goals = load_goals()
    changed = False
    completed_goals = []

    def check_and_complete(goal):
        nonlocal changed
        # If already completed or abandoned, skip
        if goal.get("status") in ["completed", "abandoned"]:
            return True

        # If has subgoals, check if ALL are complete
        if goal.get("subgoals"):
            all_done = all(check_and_complete(sub) for sub in goal["subgoals"])
            if all_done and goal.get("status") != "completed":
                mark_goal_completed(goal)
                completed_goals.append(goal)
                changed = True
                return True
            else:
                return False
        else:
            # Atomic goal: check if already done
            if goal.get("status") == "completed":
                return True
            return False

    # Top-level check for each goal
    for goal in goals:
        check_and_complete(goal)

    if changed:
        save_goals(goals)
        update_working_memory("🗂️ Ran maybe_complete_goals: marked some goals as completed.")
        if completed_goals and os.path.exists(COMPLETED_GOALS_FILE):
            # Append to completed log (optional, if file used)
            try:
                old = []
                if os.path.getsize(COMPLETED_GOALS_FILE) > 0:
                    with open(COMPLETED_GOALS_FILE, "r") as f:
                        old = json.load(f)
                with open(COMPLETED_GOALS_FILE, "w") as f:
                    json.dump(old + completed_goals, f, indent=2)
            except Exception as e:
                update_working_memory(f"⚠️ Failed to write to COMPLETED_GOALS_FILE: {e}")
    else:
        update_working_memory("maybe_complete_goals: No new goals completed.")

    return changed