def extract_current_focus_goal(focus_goal: dict) -> str:
    """
    Extracts the actual goal string from the nested focus_goal dict produced by select_focus_goals.
    Tries short_or_mid, then long_term, then top-level 'goal' (for legacy), else None.
    """
    if not isinstance(focus_goal, dict):
        return None
    # Try short_or_mid first
    short = focus_goal.get("short_or_mid")
    if isinstance(short, dict) and short.get("goal"):
        return short["goal"]
    # Fallback to long_term
    longterm = focus_goal.get("long_term")
    if isinstance(longterm, dict) and longterm.get("goal"):
        return longterm["goal"]
    # For legacy flat files
    if focus_goal.get("goal"):
        return focus_goal["goal"]
    # If all else fails
    return None