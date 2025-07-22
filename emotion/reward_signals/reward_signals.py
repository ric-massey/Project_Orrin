from emotion.reward_signals.reward_spike import log_reward_spike
from utils.json_utils import save_json
import random
from paths import EMOTIONAL_STATE_FILE, REWARD_TRACE

def release_reward_signal(
    context,
    signal_type="dopamine",
    actual_reward=1.0,
    expected_reward=0.7, 
    effort=0.5,
    mode="phasic"
):
    """
    Simulates neuromodulatory reward signals with biologically inspired behavior.
    - Supports phasic (burst) vs tonic (baseline) dopamine
    - Encodes reward prediction error (RPE)
    - Adjusts confidence, motivation, curiosity, stability
    """
    emotional_state = context.setdefault("emotional_state", {})
    reward_trace = context.setdefault("reward_trace", [])
    last_tags = context.get("last_tags", [])

    # === Reward Prediction Error ===
    rpe = actual_reward - expected_reward
    surprise = max(0.0, rpe)
    disappointment = max(0.0, -rpe)
    effort_bonus = 1.0 + effort
    strength = (surprise * effort_bonus)

    # === Dopamine (motivation + confidence)
    if signal_type == "dopamine":
        confidence_gain = 0.04 * strength
        motivation_gain = 0.07 * strength

        if mode == "phasic":
            confidence_gain *= 1.5
            motivation_gain *= 1.5

        emotional_state["confidence"] = min(1.0, emotional_state.get("confidence", 0.5) + confidence_gain)
        emotional_state["motivation"] = min(1.0, emotional_state.get("motivation", 0.5) + motivation_gain)
        log_reward_spike("dopamine", strength=strength, tags=last_tags)

    elif signal_type == "novelty":
        curiosity_gain = 0.06 * strength
        emotional_state["curiosity"] = min(1.0, emotional_state.get("curiosity", 0.5) + curiosity_gain)
        log_reward_spike("novelty", strength=strength, tags=last_tags)

    elif signal_type == "serotonin":
        stability_gain = 0.03 * strength
        emotional_state["emotional_stability"] = min(1.0, emotional_state.get("emotional_stability", 0.5) + stability_gain)
        log_reward_spike("serotonin", strength=strength, tags=last_tags)

    elif signal_type == "connection":
        connection_gain = 0.1 * strength
        emotional_state["connection"] = min(1.0, emotional_state.get("connection", 0.5) + connection_gain)
        emotional_state["curiosity"] = min(1.0, emotional_state.get("curiosity", 0.5) + (0.05 * strength))
        emotional_state["motivation"] = min(1.0, emotional_state.get("motivation", 0.5) + (0.04 * strength))
        log_reward_spike("connection", strength=strength, tags=last_tags)

    # === Store Trace
    reward_trace.append({
        "type": signal_type,
        "strength": strength,
        "actual_reward": actual_reward,
        "expected_reward": expected_reward,
        "effort": effort,
        "mode": mode,
        "tags": last_tags,
    })
    if len(reward_trace) > 50:
        reward_trace.pop(0)

    # Save to disk
    save_json(EMOTIONAL_STATE_FILE, emotional_state)
    save_json(REWARD_TRACE, reward_trace)

    return context

import random

def decay_reward_trace(context, decay_rate=0.015):
    """
    More human-like decay: adds slow/fast decay under mood, random chance for a 'sticky' reward, and purges very weak traces.
    """
    trace = context.get(REWARD_TRACE, [])
    emotional_state = context.get("emotional_state", {})
    mood = emotional_state.get("mood", "neutral")
    boredom = emotional_state.get("boredom", 0.3)
    sadness = emotional_state.get("sadness", 0.1)
    new_trace = []
    for entry in trace:
        # Mood modulation: sad = slower decay, bored = faster decay
        mod_decay = decay_rate
        if sadness > 0.6:
            mod_decay *= 0.7  # slower decay if sad
        if boredom > 0.6:
            mod_decay *= 1.5  # faster decay if bored
        # Occasional 'sticky' rewards (emotionally charged memories)
        if random.random() < 0.04:
            mod_decay *= 0.5
        entry["strength"] *= (1 - mod_decay)
        # Only keep meaningful traces (humans forget small stuff)
        if entry["strength"] > 0.03:
            new_trace.append(entry)
    context[REWARD_TRACE] = new_trace
    return context


def novelty_penalty(last_choice, current_choice, recent_choices, emotional_state=None):
    """
    Adds a more human-like, nonlinear boredom/novelty penalty:
    - Strong penalty for exact repeats, unless under stress/fear
    - Soft penalty for recent picks, more if curious/bored, less if anxious/sad
    - Nonlinear reward for breaking long ruts (the longer since last used, the more reward)
    - Occasional "moodiness" (rarely, ignore penalty entirely, like a human relapse)
    """
    # --- Moodiness: sometimes humans repeat anyway ---
    if random.random() < 0.07:  # 7% chance to ignore penalty, simulating "relapse"
        return 0.0

    # --- Strong negative for direct repeat, unless anxious/fearful ---
    if current_choice == last_choice:
        if emotional_state and emotional_state.get("anxiety", 0) > 0.6:
            return -0.1  # allow more repetition under anxiety/fear
        return -0.4

    # --- Recent repeat penalty (modulated by curiosity/boredom) ---
    recent_n = recent_choices[-4:]  # look back further for "rut"
    base_penalty = -0.18 if current_choice in recent_n else 0.0

    if emotional_state:
        boredom = emotional_state.get("boredom", 0.3)  # default low
        curiosity = emotional_state.get("curiosity", 0.5)
        # Penalize recent repeats more if bored/curious, less if content
        base_penalty *= 1 + 1.2 * (curiosity + boredom - 0.6)
        if emotional_state.get("sadness", 0) > 0.6:
            base_penalty *= 0.7  # depression = less push for novelty

    # --- Big reward for long-unpicked function ---
    if current_choice not in recent_choices:
        # The longer since it was picked, the bigger the bonus (cap at 0.4)
        length = len(recent_choices)
        last_index = recent_choices[::-1].index(current_choice) if current_choice in recent_choices else length
        reward = min(0.12 + 0.12 * last_index, 0.4)
        if emotional_state and emotional_state.get("curiosity", 0) > 0.7:
            reward *= 1.25  # ultra-curious state
        return reward

    return base_penalty