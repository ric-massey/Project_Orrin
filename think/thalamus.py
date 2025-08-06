from datetime import datetime, timezone
from utils.load_utils import load_json
from utils.append import append_to_json
from utils.log import log_activity
from utils.knowledge_utils import recall_relevant_knowledge
from think.think_utils.user_input import handle_user_input 
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import EMOTION_MODEL_FILE, ATTENTION_HISTORY

def process_inputs(context, raw_signals=None):
    """
    Orrin's thalamus: biologically inspired signal prioritization based on emotion,
    novelty, memory relevance, and dynamic goal context.
    Always pulls user input and injects as signals, so user input is never missed.
    """

    # === FIX: Bulletproof cycle_count for handle_user_input ===
    cycle_count = context.get("cycle_count", {})
    if not isinstance(cycle_count, dict) or "count" not in cycle_count:
        cycle_count = {"count": 0}

    signals, context = handle_user_input(
        context,
        cycle_count,
        context.get("long_memory", []),
        context.get("working_memory", []),
        context.get("relationships", {}),
        context.get("speaker", None)
    )
    context["raw_signals"] = signals

    # Now use signals as the prioritized raw_signals
    if raw_signals is None:
        raw_signals = context.get("raw_signals", [])

    emotional_state = context.get("emotional_state", {})
    self_model = context.get("self_model", {})
    mode = context.get("mode", {}).get("mode", "neutral")

    core_emotions = emotional_state.get("core_emotions", {})
    dominant_emotion = max(core_emotions, key=core_emotions.get, default="neutral")

    # === Load all known emotion tags dynamically ===
    emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
    known_emotions = set(emotion_model.keys())

    def emo_boost(tag):
        return round(core_emotions.get(tag, 0.0) * 0.3, 3)

    # === Memory and Directive Priming ===
    focus_keywords = recall_relevant_knowledge(
    self_model.get("core_directive", {}).get("statement", ""),
    long_memory=context.get("long_memory", []),
    working_memory=context.get("working_memory", []),
    max_items=8
    )
    directive = self_model.get("core_directive", {})
    goal_words = [w.lower() for w in directive.get("motivations", []) if isinstance(w, str)]

    # === Novelty Context — last 20 signal contents ===
    recent_signals = load_json(ATTENTION_HISTORY, default_type=list)[-20:]
    recent_contents = [r.get("content", "") for r in recent_signals if r.get("content")]

    prioritized = []

    from datetime import datetime, timezone, timedelta

    # --- Emergency interrupt support ---
    emergency_action = None
    MAX_EMERGENCY_AGE = timedelta(minutes=5)  # Only treat emergencies newer than this

    for signal in raw_signals:
        base = signal.get("signal_strength", 0.5)
        tags = signal.get("tags", [])
        content = signal.get("content", "").lower()
        source = signal.get("source", "unknown")

        # === Emergency/fire-alarm logic (never triggers on user input) ===
        if (
            ("error" in tags or "crash" in tags)
            and "user_input" not in tags
            and (
                "critical" in content or "crash" in content or "failure" in content or "emergency" in content
            )
        ):
            # --- Only if the signal is recent ---
            sig_time_str = signal.get("timestamp")
            is_recent = False
            if sig_time_str:
                try:
                    sig_time = datetime.fromisoformat(sig_time_str.replace("Z", "+00:00"))
                    is_recent = (datetime.now(timezone.utc) - sig_time) < MAX_EMERGENCY_AGE
                except Exception:
                    pass
            if is_recent:
                emergency_action = {
                    "action": "emergency_shutdown",
                    "reason": f"Fire alarm from thalamus: {content[:100]}",
                    "source_signal": signal
                }
                # --- Reward for emergency detection ---
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.7,
                    expected_reward=0.4,
                    effort=0.3,
                    mode="phasic",
                    source="emergency_signal_detected"
                )

        # === Emotion-Weighted Tag Adjustments (dynamic) ===
        for tag in tags:
            if tag in known_emotions:
                base += emo_boost(tag)

        # === Memory relevance ===
        if any(focus in content for focus in focus_keywords):
            base += 0.15

        # === Goal and mode relevance ===
        if any(goal in content for goal in goal_words):
            base += 0.15
        if mode in content:
            base += 0.1

        # === Content-based Novelty Decay (approximate) ===
        similar_contents = [c for c in recent_contents if c and c in content]
        novelty_score = max(0.0, 1.0 - (len(similar_contents) / max(1, len(recent_contents))))  # crude similarity proxy
        base += novelty_score * 0.2
        if novelty_score < 0.3:
            base -= 0.15

        # === Mild boost for boredom/errors ===
        if "boredom" in tags or "error" in tags:
            base += 0.05

        # === Final adjustments and clamping ===
        base = round(min(max(base, 0.0), 1.0), 3)
        signal["priority_score"] = base

        signal["routing_target"] = (
            "prefrontal_cortex" if "user_input" in tags else
            "auditory_cortex" if "sound" in tags else
            "visual_cortex" if "image" in tags else
            "emotion_cortex" if "emotion" in tags else
            "general"
        )

        prioritized.append(signal)

    # === If fire alarm triggered, set in context ===
    if emergency_action:
        context["emergency_action"] = emergency_action

    # === Sort and slice ===
    prioritized.sort(key=lambda s: s["priority_score"], reverse=True)
    top_signals = prioritized[:5]

    # === Attention mode logic ===
    if not raw_signals:
        attention_state = "drowsy"
    elif any("user_input" in s.get("tags", []) for s in top_signals):
        attention_state = "alert"
    elif any(s["priority_score"] > 0.6 for s in top_signals):
        attention_state = "engaged"
    elif any("internal" in s.get("tags", []) for s in top_signals):
        attention_state = "wandering"
    else:
        attention_state = "neutral"

    if not top_signals:
        log_activity("[Thalamus] No high-priority signals selected.")
        for s in prioritized[:5]:
            log_activity(f"  - Rejected: {s.get('content', '')[:80]} | Score: {s.get('priority_score', 0)}")

    log_activity(f"[Thalamus] Routed {len(top_signals)} signals | Attention mode: {attention_state}")

    for s in top_signals:
        append_to_json(ATTENTION_HISTORY, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_source": s.get("source", "unknown"),
            "content": s.get("content", ""),
            "tags": s.get("tags", []),
            "priority_score": s["priority_score"],
            "attention_mode": attention_state,
            "dominant_emotion": dominant_emotion,
            "emotional_context": core_emotions,
            "routing_target": s["routing_target"]
        })

    # === Inject back into context ===
    context["top_signals"] = top_signals
    context["attention_mode"] = attention_state

    return top_signals, attention_state