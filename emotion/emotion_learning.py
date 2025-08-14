import json
from paths import EMOTION_FUNCTION_MAP_FILE
from utils.json_utils import load_json, save_json

# Max functions to keep per emotion
MAX_ASSOCIATIONS_PER_EMOTION = 5
# Minimum times a function must be reinforced to remain (except the one we just updated)
MIN_REINFORCEMENT_THRESHOLD = 2
DECAY_RATE = 0.05  # 5% decay per update

def update_emotion_function_map(emotion: str, function_name: str, reward_signal=None):
    """
    Reinforce (emotion -> function) with optional reward scaling.
    Apply gentle decay to others. Prune rarely-used entries, but
    never drop the function we just reinforced this cycle.
    """
    if not emotion or not function_name:
        return

    # Optional normalization to avoid duplicates like "Joy" vs "joy"
    emotion_key = str(emotion).strip().lower()
    fn_key = str(function_name).strip()

    raw_map = load_json(EMOTION_FUNCTION_MAP_FILE, default_type=dict)
    if not isinstance(raw_map, dict):
        raw_map = {}

    emotion_dict = raw_map.get(emotion_key) or {}
    if not isinstance(emotion_dict, dict):
        emotion_dict = {}

    # Determine reinforcement increment scaled by reward_signal
    increment = 1.0
    if reward_signal is not None:
        try:
            increment = float(reward_signal)
            increment = max(0.1, min(increment, 5.0))  # clamp
        except Exception:
            pass

    # Decay existing counts a bit (simulate forgetting)
    for fn in list(emotion_dict.keys()):
        try:
            emotion_dict[fn] = max(0.0, float(emotion_dict[fn]) * (1 - DECAY_RATE))
        except Exception:
            # If something bad is in the file, reset that entry
            emotion_dict[fn] = 0.0

    # Reinforce the current function
    emotion_dict[fn_key] = float(emotion_dict.get(fn_key, 0.0)) + increment

    # Prune: keep top N, but don't drop the just-updated function,
    # and never prune down to zero entries.
    sorted_funcs = sorted(emotion_dict.items(), key=lambda x: x[1], reverse=True)

    pruned = {}
    for func, count in sorted_funcs:
        if len(pruned) >= MAX_ASSOCIATIONS_PER_EMOTION and func != fn_key:
            continue  # keep capacity for the updated fn if needed
        # keep entries above threshold, or the updated one regardless
        if count >= MIN_REINFORCEMENT_THRESHOLD or func == fn_key:
            pruned[func] = count

    # Ensure at least one entry remains
    if not pruned and sorted_funcs:
        # keep the highest-count entry
        best_func, best_count = sorted_funcs[0]
        pruned[best_func] = best_count

    raw_map[emotion_key] = pruned
    save_json(EMOTION_FUNCTION_MAP_FILE, raw_map)

    return pruned  # optional: return the updated mapping for this emotion