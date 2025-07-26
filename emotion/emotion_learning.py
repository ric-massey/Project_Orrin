import json
from paths import EMOTION_FUNCTION_MAP_FILE
from utils.json_utils import load_json, save_json

# Max functions to keep per emotion
MAX_ASSOCIATIONS_PER_EMOTION = 5
# Minimum times a function must be reinforced to remain
MIN_REINFORCEMENT_THRESHOLD = 2

def update_emotion_function_map(emotion, function_name, reward_signal=None):
    """
    Updates the emotion-function map by reinforcing useful functions with reward_signal scaling.
    Prunes rarely used ones to keep the mapping adaptive and relevant.
    """

    if not emotion or not function_name:
        return

    raw_map = load_json(EMOTION_FUNCTION_MAP_FILE, default_type=dict)

    if emotion not in raw_map:
        raw_map[emotion] = {}

    emotion_dict = raw_map[emotion]

    # Determine reinforcement increment scaled by reward_signal
    increment = 1.0  # default increment
    if reward_signal is not None:
        try:
            increment = float(reward_signal)
            # Clamp increment to reasonable range, e.g. 0.1 to 5.0
            increment = max(0.1, min(increment, 5.0))
        except Exception:
            pass

    # Decay existing counts slightly to simulate forgetting
    DECAY_RATE = 0.05  # 5% decay per update
    for fn in list(emotion_dict.keys()):
        emotion_dict[fn] = max(0, emotion_dict[fn] * (1 - DECAY_RATE))

    # Reinforce the function with scaled increment
    if function_name in emotion_dict:
        emotion_dict[function_name] += increment
    else:
        emotion_dict[function_name] = increment

    # Prune: keep only top N by reinforcement, and drop any below min threshold
    sorted_funcs = sorted(
        emotion_dict.items(), key=lambda x: x[1], reverse=True
    )

    pruned = {
        func: count
        for func, count in sorted_funcs[:MAX_ASSOCIATIONS_PER_EMOTION]
        if count >= MIN_REINFORCEMENT_THRESHOLD
    }

    raw_map[emotion] = pruned
    save_json(EMOTION_FUNCTION_MAP_FILE, raw_map)