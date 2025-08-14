# goals.py
from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any

from utils.json_utils import load_json, save_json, extract_json
from utils.generate_response import generate_response, get_thinking_model
from memory.working_memory import update_working_memory
from utils.log import log_activity
from emotion.reward_signals.reward_signals import release_reward_signal
from utils.signal_utils import create_signal  # instrumentation

from paths import GOALS_FILE, COMPLETED_GOALS_FILE, FOCUS_GOAL

MAX_GOALS = 15


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------
# Tree helpers
# -----------------------------

def _find_goal_by_name(tree: List[Dict], name: str) -> Optional[Dict]:
    for g in tree:
        if g.get("name") == name:
            return g
        subs = g.get("subgoals")
        if isinstance(subs, list):
            found = _find_goal_by_name(subs, name)
            if found:
                return found
    return None


def _attach_child(parent: Dict, child: Dict) -> None:
    if "subgoals" not in parent or not isinstance(parent["subgoals"], list):
        parent["subgoals"] = []
    parent["subgoals"].append(child)
    parent["last_updated"] = now_iso()


def ensure_immediate_actions_bucket(goals: List[Dict]) -> Dict:
    bucket_name = "Immediate Actions"
    for g in goals:
        if g.get("name") == bucket_name:
            return g
    bucket = {
        "name": bucket_name,
        "tier": "short_term",
        "status": "active",
        "timestamp": now_iso(),
        "last_updated": now_iso(),
        "history": ["Auto-created for micro goals"],
        "subgoals": [],
    }
    goals.append(bucket)
    return bucket


# -----------------------------
# Load / Save
# -----------------------------

def load_goals() -> List[Dict]:
    goals = load_json(GOALS_FILE, default_type=list)
    return goals if isinstance(goals, list) else []


def save_goals(goals: List[Dict]) -> None:
    # Sort by last_updated (fallback to timestamp), newest first
    def _key(g: Dict) -> str:
        return str(g.get("last_updated", g.get("timestamp", "")))

    goals_sorted = sorted(goals, key=_key, reverse=True)
    save_json(GOALS_FILE, goals_sorted[:MAX_GOALS])


# -----------------------------
# Public actions
# -----------------------------

def add_goal(goal: Dict, parent_name: Optional[str] = None) -> Dict:
    full = load_goals()
    g = dict(goal)
    now = now_iso()
    g.setdefault("status", "pending")
    g.setdefault("timestamp", now)
    g.setdefault("last_updated", now)
    g.setdefault("history", [{"event": "created", "timestamp": now}])

    parent = _find_goal_by_name(full, parent_name) if parent_name else None
    if not parent:
        parent = ensure_immediate_actions_bucket(full)

    _attach_child(parent, g)
    save_goals(full)
    return g


def create_micro_goal_for_action(action_desc: str, parent_name: Optional[str] = None) -> Dict:
    return add_goal({
        "name": action_desc.strip()[:140],
        "tier": "micro_goal",
        "status": "in_progress",
        "expected_cycles": 1,
        "history": [f"Created as micro-goal for action: {action_desc}"],
    }, parent_name=parent_name)


def mark_goal_status_by_name(name: str, new_status: str) -> bool:
    full = load_goals()
    target = _find_goal_by_name(full, name)
    if not target:
        return False
    target["status"] = new_status
    target["last_updated"] = now_iso()
    if new_status == "completed":
        target["completed_timestamp"] = now_iso()
    save_goals(full)
    return True


# -----------------------------
# Tree utils
# -----------------------------

def merge_updated_goal_into_tree(tree: List[Dict], updated: Dict) -> List[Dict]:
    """
    Merge an updated goal node into the full tree by matching (name, timestamp) or name.
    Replaces the first match found; recurses into subgoals. If not found, appends at top level.
    """
    def match(a: Dict, b: Dict) -> bool:
        return (a.get("name") == b.get("name")) and (
            a.get("timestamp") == b.get("timestamp") or not b.get("timestamp")
        )

    def replace_in_list(lst: List[Dict]) -> Tuple[List[Dict], bool]:
        out: List[Dict] = []
        replaced = False
        for g in lst:
            if not replaced and match(g, updated):
                merged = {**g, **updated}
                out.append(merged)
                replaced = True
            else:
                subs = g.get("subgoals")
                if isinstance(subs, list):
                    new_sub, sub_replaced = replace_in_list(subs)
                    if sub_replaced:
                        gg = dict(g)
                        gg["subgoals"] = new_sub
                        out.append(gg)
                        replaced = True
                        continue
                out.append(g)
        return out, replaced

    new_tree, did = replace_in_list(tree)
    if not did:
        new_tree.append(updated)
    return new_tree


# -----------------------------
# Pruning
# -----------------------------

def prune_goals(goals: List[Dict]) -> List[Dict]:
    def _parse_iso(ts: str) -> Optional[datetime]:
        try:
            if ts and isinstance(ts, str):
                # accept trailing Z
                if ts.endswith("Z"):
                    ts = ts[:-1] + "+00:00"
                return datetime.fromisoformat(ts)
        except Exception:
            pass
        return None

    def is_active(goal: Dict) -> bool:
        if goal.get("tier") == "micro_goal":
            try:
                ts = goal.get("last_updated", goal.get("timestamp"))
                dt = _parse_iso(ts)
                if dt:
                    age = (datetime.now(timezone.utc) - dt).total_seconds()
                    if goal.get("status") == "completed" and age > 600:
                        return False
                    if goal.get("status", "pending") in ("pending", "blocked") and age > 1800:
                        return False
            except Exception:
                pass
        return goal.get("status", "pending") not in {"completed", "abandoned"}

    def prune(goal: Dict) -> Dict:
        subs = goal.get("subgoals")
        if isinstance(subs, list):
            goal["subgoals"] = [prune(sub) for sub in subs if is_active(sub)]
        return goal

    return [prune(g) for g in goals if is_active(g)]


# -----------------------------
# LLM helpers
# -----------------------------

def decompose_goal(goal: Dict) -> List[Dict]:
    """
    Use the LLM to break a complex goal into actionable subgoals.
    """
    prompt = (
        "Decompose the following goal into 3-7 concrete, sequential subgoals.\n"
        f"Goal: {goal.get('name', goal.get('description', 'Unnamed'))}\n"
        'Be concise. Output JSON list of subgoals: ["", ""]'
    )
    result = generate_response(prompt, config={"model": get_thinking_model()})
    subgoals = extract_json(result or "")
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


def try_to_accomplish(goal: Dict) -> bool:
    """
    Plug in your LLM/tool integration for atomic actions.
    Returns True if succeeded, False if needs decomposition.
    """
    prompt = (
        f'Try to accomplish this atomic goal: "{goal.get("name", "")}"\n'
        'Describe outcome as JSON: {"success": true/false, "details": ""}'
    )
    result = generate_response(prompt, config={"model": get_thinking_model()})
    out = extract_json(result or "")
    if isinstance(out, dict) and out.get("success"):
        goal["status"] = "completed"
        goal["last_updated"] = now_iso()
        goal.setdefault("history", []).append({"event": "completed", "timestamp": now_iso()})
        update_working_memory(f"✅ Accomplished goal: {goal.get('name')}")
        return True
    else:
        goal.setdefault("history", []).append({"event": "failed_attempt", "timestamp": now_iso()})
        return False


# -----------------------------
# Pursuit / completion
# -----------------------------

def pursue_goal(goal: Dict) -> None:
    if goal.get("tier") == "micro_goal":
        if goal.get("status") in {"completed", "abandoned"}:
            return
        result = try_to_accomplish(goal)
        if result:
            mark_goal_completed(goal)
        else:
            goal["status"] = "blocked"
            goal["last_updated"] = now_iso()
        return

    # Composite
    subs = goal.get("subgoals")
    if isinstance(subs, list) and subs:
        for sub in subs:
            if sub.get("status", "pending") in {"pending", "in_progress", "active"}:
                pursue_goal(sub)
                return  # depth-first, one at a time
        # all subgoals done
        mark_goal_completed(goal)
    else:
        result = try_to_accomplish(goal)
        if not result:
            if not goal.get("decomposed"):
                subgoals = decompose_goal(goal)
                if subgoals:
                    goal["subgoals"] = subgoals
                    goal["decomposed"] = True
                    full_tree = load_goals()
                    full_tree = merge_updated_goal_into_tree(full_tree, goal)
                    save_goals(full_tree)
                    update_working_memory(f"🪓 Decomposed goal: {goal.get('name')}")
                    return
            else:
                update_working_memory(
                    f"⚠️ Blocked on goal: {goal.get('name')}. Needs user input or abandonment."
                )
                goal["status"] = "blocked"
                goal["last_updated"] = now_iso()


def mark_goal_completed(goal: Dict) -> None:
    goal["status"] = "completed"
    now = now_iso()
    goal["completed_timestamp"] = now
    goal["last_updated"] = now
    goal.setdefault("history", []).append({"event": "completed", "timestamp": now})
    release_reward_signal(
        context=None,
        signal_type="dopamine",
        actual_reward=1.0,
        expected_reward=0.7,
        effort=0.4,
        mode="phasic",
    )
    update_working_memory(f"🎉 Completed goal: {goal.get('name')}")
    log_activity(f"✅ Marked goal '{goal.get('name')}' as completed.")


# -----------------------------
# Focus selection
# -----------------------------

def select_focus_goals() -> Dict[str, Optional[Dict]]:
    """
    Load goals, select focus goals, and write to FOCUS_GOAL.
    Returns the focus goal dictionary.
    """
    goals = load_json(GOALS_FILE, default_type=list)
    if not isinstance(goals, list):
        goals = []

    def find_focus(goal_list: List[Dict], tier_names: List[str], collected: List[Dict], max_count: int) -> List[Dict]:
        for goal in goal_list:
            if len(collected) >= max_count:
                break
            if goal.get("status") in {"pending", "in_progress", "active"}:
                if goal.get("tier") in tier_names:
                    collected.append(goal)
                subs = goal.get("subgoals")
                if isinstance(subs, list):
                    find_focus(subs, tier_names, collected, max_count)
        return collected

    short_or_mid_goals = find_focus(goals, ["short_term", "mid_term"], [], 2)
    long_term_goals = find_focus(goals, ["long_term"], [], 1)

    focus = {
        "short_or_mid": short_or_mid_goals[0] if short_or_mid_goals else None,
        "long_term": long_term_goals[0] if long_term_goals else None,
    }

    save_json(FOCUS_GOAL, {
        "timestamp": now_iso(),
        "short_or_mid": focus["short_or_mid"],
        "long_term": focus["long_term"],
    })
    return focus


DEFAULT_LONG_TERM_NAME = "Understand self and user"

def ensure_long_term_goal(goals: List[Dict]) -> List[Dict]:
    def contains_long_term(goal_list: List[Dict]) -> bool:
        for g in goal_list:
            if g.get("tier") == "long_term" and g.get("status") in {"pending", "in_progress"}:
                return True
            subs = g.get("subgoals")
            if isinstance(subs, list) and contains_long_term(subs):
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


def update_and_select_focus_goals() -> Dict[str, Optional[Dict]]:
    goals = load_goals()
    goals = ensure_long_term_goal(goals)
    goals = prune_goals(goals)
    save_goals(goals)
    return select_focus_goals()


# -----------------------------
# Search / uniqueness
# -----------------------------

def goal_function_already_exists(goal_tree: Optional[List[Dict]], function_name: Optional[str]) -> bool:
    """
    Check if tokens of function_name appear in goal text/history anywhere in the tree.
    """
    target = re.sub(r"\W+", " ", (function_name or "")).strip().lower()
    if not target:
        return False

    def contains_fn(text: str) -> bool:
        tokens = set(re.sub(r"\W+", " ", (text or "")).strip().lower().split())
        return target in tokens

    for goal in goal_tree or []:
        hist_list = goal.get("history")
        hist_text = " ".join(
            h.get("event", "") if isinstance(h, dict) else str(h)
            for h in (hist_list if isinstance(hist_list, list) else [])
        )
        goal_text = f"{goal.get('goal','')} {goal.get('name','')} {hist_text}"
        if contains_fn(goal_text):
            return True
        subs = goal.get("subgoals")
        if isinstance(subs, list) and subs:
            if goal_function_already_exists(subs, function_name):
                return True
    return False


# -----------------------------
# Completion sweeper
# -----------------------------

def maybe_complete_goals() -> bool:
    """
    Traverses the full goal tree.
    - Marks goals as completed if all subgoals are completed.
    - Logs and rewards each completion.
    - Saves updated goals back to GOALS_FILE and appends to COMPLETED_GOALS_FILE.
    """
    goals = load_goals()
    changed = False
    completed_goals: List[Dict] = []

    # Ensure completed goals file exists as a list
    existing_completed = load_json(COMPLETED_GOALS_FILE, default_type=list)
    if not isinstance(existing_completed, list):
        existing_completed = []
        save_json(COMPLETED_GOALS_FILE, existing_completed)

    def check_and_complete(goal: Dict) -> bool:
        nonlocal changed
        # If already completed/abandoned, treat as done for parent consideration
        if goal.get("status") in {"completed", "abandoned"}:
            return True

        subs = goal.get("subgoals")
        if isinstance(subs, list) and subs:
            all_done = all(check_and_complete(sub) for sub in subs)
            if all_done and goal.get("status") != "completed":
                mark_goal_completed(goal)
                completed_goals.append(goal)
                changed = True
                return True
            return all_done
        else:
            # Atomic: done only if explicitly completed
            return goal.get("status") == "completed"

    for g in goals:
        check_and_complete(g)

    if changed:
        save_goals(goals)
        update_working_memory("🗂️ Ran maybe_complete_goals: marked some goals as completed.")
        # Append newly completed to completed goals file
        existing_completed.extend(completed_goals)
        save_json(COMPLETED_GOALS_FILE, existing_completed)
    else:
        update_working_memory("maybe_complete_goals: No new goals completed.")

    return changed