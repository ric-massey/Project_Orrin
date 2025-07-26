
import time 
import random
import math

def update_function_fatigue(context, function_name):
    fatigue = context.setdefault("function_fatigue", {})
    now = time.time()
    info = fatigue.get(function_name, {"last_used": 0, "count": 0, "score": 0.0, "fatigue_history": []})

    # Time since last use in seconds
    dt = now - info["last_used"]

    # Modulate decay based on recent mood or fatigue history
    mood_factor = 1.0
    # Example: If context has emotional state, reduce decay if motivated or excited
    emotional_state = context.get("emotional_state", {})
    motivation = emotional_state.get("motivation", 0.5)
    excitement = emotional_state.get("excitement", 0.0)
    # If motivated or excited, decay is faster (feel less fatigued)
    mood_factor -= 0.3 * (motivation + excitement)
    mood_factor = max(0.5, mood_factor)  # Clamp min decay factor

    # Fatigue decay is nonlinear: slower at first, faster later
    decay_rate_base = 0.12  # Base decay rate
    fatigue_level = info["score"]
    nonlinear_decay = decay_rate_base * math.log1p(fatigue_level + 1)

    # Adjusted decay for this update
    decay_rate = nonlinear_decay * mood_factor

    # Decay fatigue over elapsed time
    fatigue_after_decay = info["score"] * math.exp(-decay_rate * dt / 60)

    # --- Recovery boost if rested long enough ---
    if dt > 600:  # If function hasn't been used for 10 minutes
        fatigue_after_decay *= 0.85  # Additional recovery bonus

    # --- Add fatigue for recent use ---
    # Sometimes the agent "pushes through" fatigue (random chance to reduce fatigue gain)
    push_through_factor = 1.0
    if random.random() < 0.1:  # 10% chance to push through
        push_through_factor = 0.5

    fatigue_gain = 1.0 * push_through_factor
    new_fatigue = fatigue_after_decay + fatigue_gain

    # --- Keep a short history of fatigue to smooth values or detect trends ---
    fatigue_history = info.get("fatigue_history", [])
    fatigue_history.append((now, new_fatigue))
    # Keep only last 30 entries
    if len(fatigue_history) > 30:
        fatigue_history = fatigue_history[-30:]

    # Store updated info
    info.update({
        "last_used": now,
        "count": info["count"] + 1,
        "score": min(new_fatigue, 10.0),  # Cap max fatigue
        "fatigue_history": fatigue_history,
    })

    fatigue[function_name] = info
    context["function_fatigue"] = fatigue


def fatigue_penalty(context, function_name):
    fatigue = context.get("function_fatigue", {})
    info = fatigue.get(function_name, {"score": 0.0, "fatigue_history": []})
    score = info.get("score", 0.0)

    # Base penalty scales 0 (no fatigue) to -0.6 (high fatigue)
    base_penalty = -0.6 * min(1.0, score / 7.0)

    # --- Mood modulation ---
    emotional_state = context.get("emotional_state", {})
    motivation = emotional_state.get("motivation", 0.5)
    anxiety = emotional_state.get("anxiety", 0.0)
    boredom = emotional_state.get("boredom", 0.3)

    # Motivation reduces penalty (agent fights fatigue)
    motivation_factor = 1 - 0.7 * motivation  # up to 70% penalty reduction

    # Anxiety and boredom increase penalty slightly
    anxiety_factor = 1 + 0.5 * anxiety
    boredom_factor = 1 + 0.4 * boredom

    penalty = base_penalty * motivation_factor * anxiety_factor * boredom_factor

    # Occasionally the agent ignores fatigue ("mood relapse")
    if random.random() < 0.05:
        penalty = 0.0

    return penalty

def fatigue_penalty_from_context(emotional_state: dict, action_type: str) -> float:
    """
    Calculates a fatigue penalty based on Orrin's emotional state and action type.
    Returns a float penalty [0.0 - 1.0] that reduces motivation to perform the action.

    The penalty increases if fatigue or related emotions (e.g. tiredness, stress) are high.
    Certain action types (like 'physical' or 'complex') may have higher penalties.

    Args:
        emotional_state: dict containing core emotions and fatigue levels.
        action_type: str describing the type of action.

    Returns:
        float penalty between 0.0 (no penalty) and 1.0 (max penalty).
    """

    # Base fatigue value from emotional state, fallback to 0 if not tracked
    fatigue_level = emotional_state.get("fatigue", 0.0)

    # Additional emotions that might contribute to fatigue penalty
    stress = emotional_state.get("stress", 0.0)
    overwhelm = emotional_state.get("overwhelm", 0.0)

    # Combine relevant fatigue factors (weighted)
    fatigue_score = fatigue_level * 0.6 + stress * 0.3 + overwhelm * 0.1

    # Adjust penalty based on action type sensitivity
    high_effort_actions = {"physical", "complex", "long_task", "creative"}
    if action_type in high_effort_actions:
        fatigue_score *= 1.5  # Increase penalty for demanding actions

    # Clamp penalty between 0 and 1
    penalty = max(0.0, min(fatigue_score, 1.0))

    return penalty