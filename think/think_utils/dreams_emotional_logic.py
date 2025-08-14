from cognition.dreaming import compose_dream  # ✅ use compose_dream(self_model, recent)
from emotion.emotion_drift import check_emotion_drift
from behavior.behavior_generation import generate_behavior_from_integration
from emotion.update_emotional_state import update_emotional_state
from emotion.reflect_on_emotions import reflect_on_emotions
from emotion.apply_emotional_feedback import apply_emotional_feedback
from emotion.amygdala import process_emotional_signals
from memory.working_memory import update_working_memory
from emotion.reward_signals.reward_signals import release_reward_signal
from emotion.reward_signals.fatigue import update_function_fatigue
from utils.json_utils import load_json
from paths import EMOTIONAL_STATE_FILE
import json  # NEW


def dreams_and_emotional_logic(context):
    """
    Handles dreaming, drift checks, behavior generation (side effects),
    emotion reflection, feedback application, amygdala pass, and state update.
    Returns: (context, emotional_state, amygdala_response)
    """
    # Robust cycle extraction: supports int or {"count": int}
    raw_cycles = context.get("cycle_count", 0)
    cycles = raw_cycles.get("count", 0) if isinstance(raw_cycles, dict) else int(raw_cycles or 0)

    self_model = context.get("self_model", {}) or {}
    emotional_state = context.get("emotional_state", {}) or {}
    long_memory = context.get("long_memory", []) or []
    working_memory = context.get("working_memory", []) or []

    # --- Dream every 5 cycles (but not at cycle 0) ---
    if cycles > 0 and (cycles % 5 == 0):
        # Build a small "recent" list (strings) from working memory first, then long memory
        # Prefer recency and keep it short to avoid huge prompts
        wm_recent = [str(m.get("content", "")).strip() for m in working_memory[-10:] if isinstance(m, dict)]
        lm_recent = [str(m.get("content", "")).strip() for m in long_memory[-10:] if isinstance(m, dict)]
        recent = [s for s in (wm_recent + lm_recent) if s][:8]

        dream_text = compose_dream(self_model, recent)
        if dream_text:
            update_working_memory({
                "content": "Dream: " + dream_text.strip(),
                "event_type": "dream",
                "importance": 2,
                "priority": 2,
                "referenced": 0,
                "pin": False
            })
            update_function_fatigue(context, "dream")
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=0.4,
                expected_reward=0.3,
                effort=0.3,
                source="dreaming"
            )

    # --- Drift check + behavior integration (now queues proposals instead of ignoring) ---
    try:
        check_emotion_drift(context)  # if your impl accepts context
    except TypeError:
        check_emotion_drift()         # fallback to no-arg variant

    proposals = generate_behavior_from_integration(context)  # now captured
    if isinstance(proposals, list) and proposals:
        # Clean + de-dup against any existing queued proposals
        existing = context.get("behavior_proposals", [])
        def _key(a: dict):
            if not isinstance(a, dict):
                return None
            return (
                a.get("type"),
                a.get("description"),
                json.dumps(a.get("content", None), sort_keys=True, default=str)
            )
        seen = { _key(a) for a in existing if isinstance(a, dict) }
        new = []
        for a in proposals:
            if not isinstance(a, dict) or not a.get("type"):
                continue
            k = _key(a)
            if k not in seen:
                new.append(a)
                seen.add(k)

        if new:
            # Prepend new ones for recency; keep queue small
            context["behavior_proposals"] = (new + existing)[:12]
            update_working_memory({
                "content": f"🧩 Queued {len(new)} behavior proposal(s) for scoring.",
                "event_type": "behavior_proposals",
                "importance": 1,
                "priority": 1,
            })

    # --- Reflect on emotions (every 10 cycles or low stability) ---
    if (cycles % 10 == 0) or (emotional_state.get("emotional_stability", 1.0) < 0.6):
        reflect_on_emotions(context, self_model, long_memory)

    # --- Apply feedback and process amygdala ---
    maybe_ctx = apply_emotional_feedback(context)
    if isinstance(maybe_ctx, dict):
        context = maybe_ctx

    context, amygdala_response = process_emotional_signals(context)

    # --- Update emotional state and refresh from disk ---
    try:
        update_emotional_state(context)  # preferred signature
    except TypeError:
        update_emotional_state()         # fallback to no-arg variant

    emotional_state = load_json(EMOTIONAL_STATE_FILE, default_type=dict) or {}
    context["emotional_state"] = emotional_state  # mirror fresh state

    return context, emotional_state, amygdala_response
