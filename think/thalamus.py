from datetime import datetime, timezone, timedelta
from utils.load_utils import load_json
from utils.log import log_activity
from utils.knowledge_utils import recall_relevant_knowledge
from think.think_utils.user_input import handle_user_input
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import EMOTION_MODEL_FILE, ATTENTION_HISTORY
from utils.json_utils import save_json
from utils.signal_utils import gather_signals  # <-- added


def _as_strings(items):
    """Coerce recall results into a list of lowercase strings for containment checks."""
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it.lower())
        elif isinstance(it, dict):
            # prefer 'content' if present, else stringify
            s = str(it.get("content", it))
            if s:
                out.append(s.lower())
        else:
            out.append(str(it).lower())
    return out


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

    # Pull user input → signals
    signals, context = handle_user_input(
        context,
        cycle_count,
        context.get("long_memory", []),
        context.get("working_memory", []),
        context.get("relationships", {}),
        context.get("speaker", None),
    )

    # Also gather subsystem signals
    try:
        signals.extend(gather_signals(context) or [])
    except Exception:
        # don't let a subsystem failure break input processing
        pass

    context["raw_signals"] = signals

    # Use signals as raw_signals if not provided
    if raw_signals is None:
        raw_signals = context.get("raw_signals", [])

    emotional_state = context.get("emotional_state", {}) or {}
    self_model = context.get("self_model", {}) or {}
    mode = (context.get("mode", {}) or {}).get("mode", "neutral")

    core_emotions = emotional_state.get("core_emotions", {}) or {}
    dominant_emotion = max(core_emotions, key=core_emotions.get) if core_emotions else "neutral"

    # === Load all known emotion tags dynamically ===
    emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
    known_emotions = set(emotion_model.keys()) if isinstance(emotion_model, dict) else set()

    def emo_boost(tag: str) -> float:
        return round(float(core_emotions.get(tag, 0.0)) * 0.3, 3)

    # === Memory and Directive Priming ===
    directive = self_model.get("core_directive", {}) or {}
    directive_stmt = directive.get("statement", "") or ""
    try:
        focus_related = recall_relevant_knowledge(
            directive_stmt,
            long_memory=context.get("long_memory", []),
            working_memory=context.get("working_memory", []),
            max_items=8,
        )
    except Exception:
        focus_related = []
    focus_texts = _as_strings(focus_related)

    goal_words = [w.lower() for w in directive.get("motivations", []) if isinstance(w, str)]

    # === Novelty Context — last 20 signal contents ===
    recent_signals = load_json(ATTENTION_HISTORY, default_type=list)
    if not isinstance(recent_signals, list):
        recent_signals = []
    recent_contents = [
        (r.get("content") or "").lower()
        for r in recent_signals[-20:]
        if isinstance(r, dict)
    ]

    prioritized = []

    # --- Emergency interrupt support ---
    emergency_action = None
    MAX_EMERGENCY_AGE = timedelta(minutes=5)  # Only treat emergencies newer than this

    for signal in raw_signals or []:
        if not isinstance(signal, dict):
            continue

        base = float(signal.get("signal_strength", 0.5) or 0.5)
        tags = signal.get("tags", []) or []
        if not isinstance(tags, list):
            tags = [tags]
        content = (signal.get("content") or "").lower()
        source = signal.get("source", "unknown")

        # === Emergency/fire-alarm logic (never triggers on user input) ===
        if (
            any(t in {"error", "crash"} for t in tags)
            and "user_input" not in tags
            and any(k in content for k in ("critical", "crash", "failure", "emergency"))
        ):
            # Only if the signal is recent
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
                    "source_signal": signal,
                }
                # Reward for emergency detection
                try:
                    release_reward_signal(
                        context,
                        signal_type="dopamine",
                        actual_reward=0.7,
                        expected_reward=0.4,
                        effort=0.3,
                        mode="phasic",
                        source="emergency_signal_detected",
                    )
                except Exception:
                    pass

        # === Emotion-Weighted Tag Adjustments (dynamic) ===
        for tag in tags:
            if tag in known_emotions:
                base += emo_boost(tag)

        # === Memory relevance (use strings distilled from recall results) ===
        if any(ft and ft in content for ft in focus_texts):
            base += 0.15

        # === Goal and mode relevance ===
        if any(gw and gw in content for gw in goal_words):
            base += 0.15
        if mode and mode in content:
            base += 0.1

        # === Content-based Novelty Decay (approximate) ===
        # crude containment similarity against recent contents
        similar_contents = [c for c in recent_contents if c and c in content]
        novelty_score = max(0.0, 1.0 - (len(similar_contents) / max(1, len(recent_contents))))
        base += novelty_score * 0.2
        if novelty_score < 0.3:
            base -= 0.15

        # === Mild boost for boredom/errors ===
        if any(t in {"boredom", "error"} for t in tags):
            base += 0.05

        # === Final adjustments and clamping ===
        base = round(min(max(base, 0.0), 1.0), 3)
        signal["priority_score"] = base

        # routing target
        signal_tags = set(tags)
        if "user_input" in signal_tags:
            rt = "prefrontal_cortex"
        elif "sound" in signal_tags:
            rt = "auditory_cortex"
        elif "image" in signal_tags:
            rt = "visual_cortex"
        elif "emotion" in signal_tags:
            rt = "emotion_cortex"
        else:
            rt = "general"
        signal["routing_target"] = rt

        prioritized.append(signal)

    # === If fire alarm triggered, set in context ===
    if emergency_action:
        context["emergency_action"] = emergency_action

    # === Sort and slice ===
    prioritized.sort(key=lambda s: s.get("priority_score", 0.0), reverse=True)
    top_signals = prioritized[:5]

    # === Attention mode logic ===
    if not raw_signals:
        attention_state = "drowsy"
    elif any("user_input" in (s.get("tags") or []) for s in top_signals):
        attention_state = "alert"
    elif any(s.get("priority_score", 0.0) > 0.6 for s in top_signals):
        attention_state = "engaged"
    elif any("internal" in (s.get("tags") or []) for s in top_signals):
        attention_state = "wandering"
    else:
        attention_state = "neutral"

    if not top_signals:
        log_activity("[Thalamus] No high-priority signals selected.")
        for s in prioritized[:5]:
            log_activity(f"  - Rejected: {(s.get('content') or '')[:80]} | Score: {s.get('priority_score', 0)}")

    log_activity(f"[Thalamus] Routed {len(top_signals)} signals | Attention mode: {attention_state}")

    # === Persist attention history (cap to last 500) ===
    history = load_json(ATTENTION_HISTORY, default_type=list)
    if not isinstance(history, list):
        history = []

    new_records = []
    for s in top_signals:
        new_records.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_source": s.get("source", "unknown"),
            "content": s.get("content", ""),
            "tags": s.get("tags", []),
            "priority_score": s.get("priority_score", 0.0),
            "attention_mode": attention_state,
            "dominant_emotion": dominant_emotion,
            "emotional_context": core_emotions,
            "routing_target": s.get("routing_target", "general"),
        })

    history.extend(new_records)
    if len(history) > 500:
        history = history[-500:]
    save_json(ATTENTION_HISTORY, history)

    # === Inject back into context ===
    context["top_signals"] = top_signals
    context["attention_mode"] = attention_state

    return top_signals, attention_state