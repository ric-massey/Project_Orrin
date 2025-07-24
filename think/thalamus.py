# cognition/thalamus.py

from datetime import datetime, timezone
from difflib import SequenceMatcher
from utils.log import log_activity
from utils.json_utils import load_json
from utils.append import append_to_json
from utils.knowledge_utils import recall_relevant_knowledge
from paths import ATTENTION_HISTORY, EMOTION_MODEL_FILE

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def calculate_novelty(content, recent_contents):
    if not recent_contents:
        return 1.0
    similarities = [similarity(content.lower(), r.lower()) for r in recent_contents]
    return round(1.0 - max(similarities, default=0.0), 3)

def process_inputs(raw_signals, context):
    """
    Orrin's thalamus: biologically inspired signal prioritization based on emotion,
    novelty, memory relevance, and dynamic goal context.
    """
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
    focus_keywords = recall_relevant_knowledge(emotional_state, max_items=5)
    directive = self_model.get("core_directive", {})
    goal_words = [w.lower() for w in directive.get("motivations", []) if isinstance(w, str)]

    # === Novelty Context — last 20 signal contents ===
    recent_signals = load_json(ATTENTION_HISTORY, default_type=list)[-20:]
    recent_contents = [r.get("content", "") for r in recent_signals if r.get("content")]

    prioritized = []

    for signal in raw_signals:
        base = signal.get("signal_strength", 0.5)
        tags = signal.get("tags", [])
        content = signal.get("content", "").lower()
        source = signal.get("source", "unknown")

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

        # === Content-based Novelty Decay ===
        novelty_score = calculate_novelty(content, recent_contents)
        base += novelty_score * 0.2  # Amplify true novelty
        if novelty_score < 0.3:
            base -= 0.15  # Penalize redundancy

        # === Boredom and error get minor reward to prevent dormancy ===
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

    # === Sort + select ===
    prioritized.sort(key=lambda s: s["priority_score"], reverse=True)
    top_signals = prioritized[:5]

    # === Improved attention state logic ===
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

    # === Write to context for higher-level reasoning ===
    context["top_signals"] = top_signals
    context["attention_mode"] = attention_state

    return top_signals, attention_state