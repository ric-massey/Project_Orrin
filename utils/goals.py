from typing import Optional

def extract_current_focus_goal(focus_goal: dict) -> Optional[str]:
    """
    Extracts the actual goal string from the nested focus_goal dict produced by select_focus_goals.
    Tries short_or_mid, then long_term, then top-level 'goal' (for legacy), else None.
    """
    if not isinstance(focus_goal, dict):
        return None

    # Try short_or_mid first
    short = focus_goal.get("short_or_mid")
    if isinstance(short, dict) and isinstance(short.get("name"), str):
        return short["name"].strip()

    # Fallback to long_term
    longterm = focus_goal.get("long_term")
    if isinstance(longterm, dict) and isinstance(longterm.get("name"), str):
        return longterm["name"].strip()

    # For legacy flat files
    if isinstance(focus_goal.get("goal"), str):
        return focus_goal["goal"].strip()

    # If all else fails
    return None