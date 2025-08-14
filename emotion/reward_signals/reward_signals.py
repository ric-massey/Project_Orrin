from datetime import datetime, timezone
import time
import random

from emotion.reward_signals.reward_spike import log_reward_spike
from utils.json_utils import save_json
from utils.log import log_activity
from utils.signal_utils import create_signal
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
    """
    Update in-memory emotional state + reward trace and persist both to disk.
    Uses context['reward_trace'] (string key) for the live buffer and REWARD_TRACE (Path) for disk.
    """

    emotional_state = context.setdefault("emotional_state", {})
    reward_trace = context.setdefault("reward_trace", [])
    last_tags = context.get("last_tags", [])

    # --- Reward Prediction Error (RPE) with noise ---
    rpe = actual_reward - expected_reward
    noise = random.gauss(0, 0.05)
    rpe_noisy = max(min(rpe + noise, 1.0), -1.0)

    surprise = max(0.0, rpe_noisy)
    disappointment = max(0.0, -rpe_noisy)

    # --- Effort modulation (clamped) ---
    fatigue = emotional_state.get("fatigue", 0.0)
    motivation = emotional_state.get("motivation", 0.5)
    effort_modulated = effort * (1 - fatigue) * (0.5 + motivation)
    # clamp effort bonus so it doesn't explode
    effort_bonus = min(max(1.0 + effort_modulated, 0.2), 2.0)

    strength = surprise * effort_bonus

    # === Dopamine ===
    if signal_type == "dopamine":
        serotonin = emotional_state.get("serotonin", 0.5)
        anxiety = emotional_state.get("anxiety", 0.0)

        base_confidence_gain = 0.04 * strength
        base_motivation_gain = 0.07 * strength

        serotonin_mod = 1 - 0.5 * (1 - serotonin)
        anxiety_mod = 1 - 0.6 * anxiety

        confidence_gain = base_confidence_gain * serotonin_mod * anxiety_mod
        motivation_gain = base_motivation_gain * serotonin_mod * anxiety_mod

        if mode == "phasic":
            confidence_gain *= 1.7 + random.uniform(-0.2, 0.2)
            motivation_gain *= 1.7 + random.uniform(-0.2, 0.2)

        emotional_state["confidence"] = min(1.0, emotional_state.get("confidence", 0.5) + confidence_gain)
        emotional_state["motivation"] = min(1.0, emotional_state.get("motivation", 0.5) + motivation_gain)

        if rpe_noisy > 0.5 and random.random() < 0.15:
            context.setdefault("raw_signals", []).append(
                create_signal(
                    source="dopamine_burst",
                    content="Unexpected dopamine burst despite moderate surprise!",
                    signal_strength=0.9,
                    tags=["dopamine", "burst", "impulse"],
                )
            )

        log_reward_spike("dopamine", strength=strength, tags=last_tags)

    # === Novelty ===
    elif signal_type == "novelty":
        base_curiosity_gain = 0.06 * strength
        boredom = emotional_state.get("boredom", 0.3)
        curiosity = emotional_state.get("curiosity", 0.5)

        curiosity_gain = base_curiosity_gain * (1 + 0.5 * boredom) * (1 - fatigue)
        emotional_state["curiosity"] = min(1.0, curiosity + curiosity_gain)

        log_reward_spike("novelty", strength=strength, tags=last_tags)

    # === Serotonin ===
    elif signal_type == "serotonin":
        base_stability_gain = 0.03 * strength
        stress = emotional_state.get("stress", 0.0)
        stability_gain = base_stability_gain * (1 - 0.7 * stress)
        emotional_state["emotional_stability"] = min(
            1.0, emotional_state.get("emotional_stability", 0.5) + stability_gain
        )

        log_reward_spike("serotonin", strength=strength, tags=last_tags)

    # === Connection ===
    elif signal_type == "connection":
        base_connection_gain = 0.1 * strength
        emotional_state["connection"] = min(1.0, emotional_state.get("connection", 0.5) + base_connection_gain)
        emotional_state["curiosity"] = min(1.0, emotional_state.get("curiosity", 0.5) + (0.05 * strength))
        emotional_state["motivation"] = min(1.0, emotional_state.get("motivation", 0.5) + (0.04 * strength))

        log_reward_spike("connection", strength=strength, tags=last_tags)

    # === Impulsive burst on big RPE ===
    if abs(rpe_noisy) > 0.8 and random.random() < 0.7:
        impulse = create_signal(
            source="reward_impulse",
            content="Sudden spike of motivation/novelty! Dopamine burst.",
            signal_strength=0.97,
            tags=["novelty", "impulse", "dopamine_spike", "action"],
        )
        context.setdefault("raw_signals", []).append(impulse)
        log_activity(f"💥 Dopamine burst! Injected novelty impulse into thalamus: {impulse}")

    # Optionally cap raw_signals growth
    if len(context.get("raw_signals", [])) > 200:
        context["raw_signals"] = context["raw_signals"][-200:]

    # === Append to in-memory trace and persist ===
    noisy_strength = strength * random.uniform(0.85, 1.15)
    reward_trace.append({
        "type": signal_type,
        "strength": noisy_strength,
        "actual_reward": actual_reward,
        "expected_reward": expected_reward,
        "effort": effort,
        "mode": mode,
        "tags": last_tags,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
    })
    if len(reward_trace) > 50:
        reward_trace.pop(0)

    # Persist emotional state + trace
    save_json(EMOTIONAL_STATE_FILE, emotional_state)
    save_json(REWARD_TRACE, reward_trace)

    return context


def decay_reward_trace(context, base_decay_rate=0.015):
    """
    Decay the in-memory reward trace stored under context['reward_trace'].
    Also persists the decayed trace back to REWARD_TRACE on disk.
    """
    trace = context.get("reward_trace", [])
    emotional_state = context.get("emotional_state", {})

    boredom = emotional_state.get("boredom", 0.3)
    sadness = emotional_state.get("sadness", 0.1)
    anxiety = emotional_state.get("anxiety", 0.1)
    fatigue = emotional_state.get("fatigue", 0.2)
    arousal = emotional_state.get("arousal", 0.2)

    current_time = time.time()
    new_trace = []

    for entry in trace:
        mod_decay = base_decay_rate

        if sadness > 0.6:
            mod_decay *= 0.7
        if boredom > 0.6:
            mod_decay *= 1.5
        if anxiety > 0.7:
            mod_decay *= 0.9

        mod_decay *= 1 + fatigue * 0.5

        salience = entry.get("salience", 1.0)
        mod_decay /= max(salience, 0.1)

        if random.random() < 0.05 * arousal:
            mod_decay *= 0.5

        last_ref = entry.get("last_referenced_time", 0.0)
        time_since_ref = current_time - last_ref
        if time_since_ref < 300:
            mod_decay *= 0.3

        entry["strength"] *= (1 - mod_decay) ** 2

        if entry["strength"] > 0.03:
            new_trace.append(entry)

    context["reward_trace"] = new_trace
    # persist decayed buffer so it survives restarts
    save_json(REWARD_TRACE, new_trace)
    return context


def novelty_penalty(last_choice, current_choice, recent_choices, emotional_state=None, context=None):
    """
    Soft boredom/novelty penalty or reward for action selection.
    Negative for repetition, positive for breaking ruts.
    """
    if emotional_state is None:
        emotional_state = {}
    if context is None:
        context = {}

    # Moodiness: occasionally ignore penalty (7%)
    if random.random() < 0.07:
        return 0.0

    anxiety = emotional_state.get("anxiety", 0.0)
    fear = emotional_state.get("fear", 0.0)
    boredom = emotional_state.get("boredom", 0.3)
    curiosity = emotional_state.get("curiosity", 0.5)
    sadness = emotional_state.get("sadness", 0.0)
    excitement = emotional_state.get("excitement", 0.0)
    motivation = emotional_state.get("motivation", 0.5)
    fatigue = emotional_state.get("fatigue", 0.0)

    # derivative of boredom
    context.setdefault("boredom_history", [])
    context["boredom_history"].append(boredom)
    if len(context["boredom_history"]) > 6:
        context["boredom_history"] = context["boredom_history"][-6:]

    if len(context["boredom_history"]) > 1:
        delta_boredom = context["boredom_history"][-1] - context["boredom_history"][-2]
    else:
        delta_boredom = 0.0

    context.setdefault("boredom_deltas", [])
    context["boredom_deltas"].append(delta_boredom)
    if len(context["boredom_deltas"]) > 5:
        context["boredom_deltas"] = context["boredom_deltas"][-5:]
    smoothed_deriv = sum(context["boredom_deltas"]) / len(context["boredom_deltas"])

    # hard repeat penalty
    if current_choice == last_choice:
        if anxiety > 0.6 or fear > 0.5 or motivation > 0.7:
            return -0.1
        penalty = -0.4 - fatigue * 0.2
        return max(penalty, -0.7)

    # soft penalty for recent repeats
    recent_n = recent_choices[-4:]
    base_penalty = -0.18 if current_choice in recent_n else 0.0

    emotion_mod = (curiosity + boredom) - (anxiety + fear + sadness)
    if sadness > 0.6:
        emotion_mod *= 0.6
    if excitement > 0.5 or motivation > 0.7:
        emotion_mod *= -0.8
    base_penalty *= (1 + 1.5 * emotion_mod)

    # derivative softly modulates
    if abs(smoothed_deriv) > 0.03:
        deriv_effect = min(max(smoothed_deriv, -0.12), 0.12)
        base_penalty = 0.85 * base_penalty + 0.15 * (base_penalty * (1.0 + deriv_effect * 2.5))

    # reward for breaking ruts
    if current_choice not in recent_choices:
        length = len(recent_choices)
        last_index = recent_choices[::-1].index(current_choice) if current_choice in recent_choices else length
        reward = min(0.15 + 0.15 * last_index, 0.5)
        boost = curiosity * 0.4 + excitement * 0.3 + motivation * 0.3
        reward *= 1 + boost
        reward = min(reward, 0.7)
        if smoothed_deriv > 0.08:
            reward += min(smoothed_deriv * 0.11, 0.07)
        return reward

    return base_penalty