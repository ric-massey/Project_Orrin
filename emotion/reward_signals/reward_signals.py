from emotion.reward_signals.reward_spike import log_reward_spike
from utils.json_utils import save_json
from utils.log import log_activity 
from datetime import datetime, timezone
import random
from paths import EMOTIONAL_STATE_FILE, REWARD_TRACE

def release_reward_signal(
    context,
    signal_type="dopamine",
    actual_reward=1.0,
    expected_reward=0.7,
    effort=0.5,
    mode="phasic",
    source=None
):
    emotional_state = context.setdefault("emotional_state", {})
    reward_trace = context.setdefault("reward_trace", [])
    last_tags = context.get("last_tags", [])

    # === Reward Prediction Error (RPE) with noise ===
    rpe = actual_reward - expected_reward
    # Add some noise to RPE to simulate variability
    noise = random.gauss(0, 0.05)
    rpe_noisy = max(min(rpe + noise, 1.0), -1.0)

    surprise = max(0.0, rpe_noisy)
    disappointment = max(0.0, -rpe_noisy)

    # Effort can be modulated by fatigue or motivation
    fatigue = emotional_state.get("fatigue", 0.0)  # New fatigue level (0 to 1)
    motivation = emotional_state.get("motivation", 0.5)

    effort_modulated = effort * (1 - fatigue) * (0.5 + motivation)  # reduce if fatigued, increase if motivated
    effort_bonus = 1.0 + effort_modulated

    strength = surprise * effort_bonus

    # === Dopamine signal with modulation ===
    if signal_type == "dopamine":
        # Dopamine gain modulated by serotonin and anxiety
        serotonin = emotional_state.get("serotonin", 0.5)
        anxiety = emotional_state.get("anxiety", 0.0)

        base_confidence_gain = 0.04 * strength
        base_motivation_gain = 0.07 * strength

        # Serotonin reduces impulsivity but stabilizes dopamine
        serotonin_mod = 1 - 0.5 * (1 - serotonin)
        anxiety_mod = 1 - 0.6 * anxiety  # Anxiety blunts dopamine

        confidence_gain = base_confidence_gain * serotonin_mod * anxiety_mod
        motivation_gain = base_motivation_gain * serotonin_mod * anxiety_mod

        if mode == "phasic":
            confidence_gain *= 1.7 + random.uniform(-0.2, 0.2)  # add small variability
            motivation_gain *= 1.7 + random.uniform(-0.2, 0.2)

        # Increment dopamine related states, capped at 1.0
        emotional_state["confidence"] = min(1.0, emotional_state.get("confidence", 0.5) + confidence_gain)
        emotional_state["motivation"] = min(1.0, emotional_state.get("motivation", 0.5) + motivation_gain)

        # Occasionally trigger burst even if surprise moderate
        if rpe_noisy > 0.5 and random.random() < 0.15:
            context.setdefault("raw_signals", []).append({
                "source": "dopamine_burst",
                "content": "Unexpected dopamine burst despite moderate surprise!",
                "signal_strength": 0.9,
                "tags": ["dopamine", "burst", "impulse"]
            })

        log_reward_spike("dopamine", strength=strength, tags=last_tags)

    elif signal_type == "novelty":
        base_curiosity_gain = 0.06 * strength
        # Curiosity modulated by boredom and fatigue
        boredom = emotional_state.get("boredom", 0.3)
        curiosity = emotional_state.get("curiosity", 0.5)

        curiosity_gain = base_curiosity_gain * (1 + 0.5 * boredom) * (1 - fatigue)
        emotional_state["curiosity"] = min(1.0, curiosity + curiosity_gain)

        log_reward_spike("novelty", strength=strength, tags=last_tags)

    elif signal_type == "serotonin":
        base_stability_gain = 0.03 * strength
        # Serotonin gain influenced by stress (reduce if stressed)
        stress = emotional_state.get("stress", 0.0)
        stability_gain = base_stability_gain * (1 - 0.7 * stress)
        emotional_state["emotional_stability"] = min(1.0, emotional_state.get("emotional_stability", 0.5) + stability_gain)

        log_reward_spike("serotonin", strength=strength, tags=last_tags)

    elif signal_type == "connection":
        base_connection_gain = 0.1 * strength
        emotional_state["connection"] = min(1.0, emotional_state.get("connection", 0.5) + base_connection_gain)

        # Also boost related states but modulated
        emotional_state["curiosity"] = min(1.0, emotional_state.get("curiosity", 0.5) + (0.05 * strength))
        emotional_state["motivation"] = min(1.0, emotional_state.get("motivation", 0.5) + (0.04 * strength))

        log_reward_spike("connection", strength=strength, tags=last_tags)

    # === New: Impulsive dopamine burst probabilistic ===
    if abs(rpe_noisy) > 0.8 and random.random() < 0.7:
        impulse = {
            "source": "reward_impulse",
            "content": "Sudden spike of motivation/novelty! Dopamine burst.",
            "signal_strength": 0.97,
            "tags": ["novelty", "impulse", "dopamine_spike", "action"]
        }
        context.setdefault("raw_signals", []).append(impulse)
        log_activity(f"💥 Dopamine burst! Injected novelty impulse into thalamus: {impulse}")

    # === Store Trace with noise in strength to simulate imperfect memory ===
    noisy_strength = strength * random.uniform(0.85, 1.15)
    reward_trace.append({
        "type": signal_type,
        "strength": noisy_strength,
        "actual_reward": actual_reward,
        "expected_reward": expected_reward,
        "effort": effort,
        "mode": mode,
        "tags": last_tags,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    if len(reward_trace) > 50:
        reward_trace.pop(0)

    # Save to disk
    save_json(EMOTIONAL_STATE_FILE, emotional_state)
    save_json(REWARD_TRACE, reward_trace)

    return context


import time
import random
from paths import REWARD_TRACE

def decay_reward_trace(context, base_decay_rate=0.015):
    trace = context.get(REWARD_TRACE, [])
    emotional_state = context.get("emotional_state", {})

    # Extract relevant emotional/internal states with defaults
    mood = emotional_state.get("mood", "neutral")
    boredom = emotional_state.get("boredom", 0.3)
    sadness = emotional_state.get("sadness", 0.1)
    anxiety = emotional_state.get("anxiety", 0.1)
    fatigue = emotional_state.get("fatigue", 0.2)
    arousal = emotional_state.get("arousal", 0.2)  # emotional arousal level

    current_time = time.time()
    new_trace = []

    for entry in trace:
        mod_decay = base_decay_rate

        # Emotional modulation of decay
        if sadness > 0.6:
            mod_decay *= 0.7  # slower decay when sad (rumination)
        if boredom > 0.6:
            mod_decay *= 1.5  # faster decay when bored (less attention)
        if anxiety > 0.7:
            mod_decay *= 0.9  # slightly slower forgetting under anxiety

        # Fatigue effect: more fatigue speeds decay (less cognitive energy)
        mod_decay *= 1 + fatigue * 0.5

        # Memory salience (importance/emotional charge) slows decay
        salience = entry.get("salience", 1.0)  # default neutral salience
        mod_decay /= max(salience, 0.1)  # avoid division by zero, higher salience = slower decay

        # Arousal boosts stickiness probabilistically (emotional events stick more)
        if random.random() < 0.05 * arousal:
            mod_decay *= 0.5

        # Memory rehearsal effect: if recently referenced, decay slows drastically
        last_ref = entry.get("last_referenced_time", 0)
        time_since_ref = current_time - last_ref
        if time_since_ref < 300:  # 5 minutes rehearsal window
            mod_decay *= 0.3

        # Nonlinear decay: exponential style for smoother forgetting curve
        entry["strength"] *= (1 - mod_decay) ** 2

        # Keep only meaningful traces above threshold (simulate forgetting)
        if entry["strength"] > 0.03:
            new_trace.append(entry)

    context[REWARD_TRACE] = new_trace
    return context

def novelty_penalty(last_choice, current_choice, recent_choices, emotional_state=None):
    """
    More nuanced human-like boredom/novelty penalty:
    - Strong penalty for exact repeats unless under anxiety/fear or high motivation
    - Soft penalty for recent picks, modulated by boredom, curiosity, anxiety, fear, sadness, excitement, motivation
    - Nonlinear reward for breaking long ruts, boosted by curiosity and excitement
    - Occasional moodiness (rarely ignore penalty entirely, simulating relapse)
    - Fatigue and stress modulate penalties/rewards
    """
    if emotional_state is None:
        emotional_state = {}

    # --- Moodiness: occasionally ignore penalty (7%) ---
    if random.random() < 0.07:
        return 0.0

    anxiety = emotional_state.get("anxiety", 0)
    fear = emotional_state.get("fear", 0)
    boredom = emotional_state.get("boredom", 0.3)
    curiosity = emotional_state.get("curiosity", 0.5)
    sadness = emotional_state.get("sadness", 0)
    excitement = emotional_state.get("excitement", 0)
    motivation = emotional_state.get("motivation", 0.5)
    fatigue = emotional_state.get("fatigue", 0)  # You can define this or pass in from fatigue tracking

    # --- Strong negative for direct repeat ---
    if current_choice == last_choice:
        # Allow more repetition under anxiety/fear/motivation
        if anxiety > 0.6 or fear > 0.5 or motivation > 0.7:
            return -0.1
        # Heavier penalty if fatigued
        penalty = -0.4 - fatigue * 0.2
        return max(penalty, -0.7)  # Cap max penalty

    # --- Soft penalty for recent repeats ---
    recent_n = recent_choices[-4:]
    base_penalty = -0.18 if current_choice in recent_n else 0.0

    # Modulate penalty with emotional state
    emotion_mod = (curiosity + boredom) - (anxiety + fear + sadness)
    # If sad, decrease push for novelty (less penalty)
    if sadness > 0.6:
        emotion_mod *= 0.6
    # If excited or highly motivated, decrease penalty or even flip to reward
    if excitement > 0.5 or motivation > 0.7:
        emotion_mod *= -0.8  # Flip to positive effect

    base_penalty *= (1 + 1.5 * emotion_mod)

    # --- Reward for breaking long ruts ---
    if current_choice not in recent_choices:
        length = len(recent_choices)
        last_index = recent_choices[::-1].index(current_choice) if current_choice in recent_choices else length
        reward = min(0.15 + 0.15 * last_index, 0.5)  # Slightly higher max reward
        # Boost reward with curiosity, excitement, and motivation
        boost = curiosity * 0.4 + excitement * 0.3 + motivation * 0.3
        reward *= 1 + boost
        # Cap reward at 0.7 max
        reward = min(reward, 0.7)
        return reward

    # --- Default fallback penalty ---
    return base_penalty

