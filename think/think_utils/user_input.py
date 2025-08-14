from utils.timing import update_last_active
from emotion.reward_signals.reward_signals import release_reward_signal
from memory.chat_log import log_raw_user_input, get_user_input, summarize_chat_to_long_memory
from utils.log import read_recent_errors_txt, read_recent_errors_json
from cognition.selfhood.boundary_check import check_violates_boundaries
import random
from paths import CHAT_LOG_FILE, ERROR_FILE, MODEL_FAILURES_JSON, LONG_MEMORY_FILE
from utils.signal_utils import create_signal  # <-- added

def log_user_input_once(user_input, context):
    if not user_input or not user_input.strip():
        return
    stripped = user_input.strip()
    if stripped in {"—", "-", "--", "---"}:
        return
    last_logged = context.get("last_logged_user_input", "")
    if stripped == (last_logged or "").strip():
        return
    context["last_logged_user_input"] = stripped
    log_raw_user_input(stripped)

def is_real_user_input(user_input):
    if not user_input:
        return False
    test = user_input.strip()
    return bool(test) and test not in {"—", "-", "--", "---"}

def handle_user_input(
    context,
    cycle_count,
    long_memory,      # kept in signature (unused here; file path is used instead)
    working_memory,   # kept for parity with caller
    relationships,
    speaker=None
):
    user_input = get_user_input()
    context["latest_user_input"] = user_input

    # Log user input once here, before any processing
    log_user_input_once(user_input, context)

    raw_signals = []

    # relationships may be None
    rel_map = relationships or {}
    user_id = context.get("user_id", "user")
    rel_data = rel_map.get(user_id, {"influence_score": 0.5, "recent_emotional_effect": "neutral"})
    influence = rel_data.get("influence_score", 0.5)
    emotional_effect = rel_data.get("recent_emotional_effect", "")

    curiosity = context.get("emotional_state", {}).get("curiosity", 0.5)
    dynamic_signal_strength = round(0.3 + 0.4 * curiosity + 0.2 * float(influence), 3)

    if is_real_user_input(user_input):
        release_reward_signal(
            context,
            signal_type="connection",
            actual_reward=1.0,
            expected_reward=0.4,
            effort=0.2,
            mode="phasic",
            source="user_input_received"
        )
        raw_signals.append(create_signal(
            source="user_input",
            content=user_input,
            signal_strength=min(dynamic_signal_strength, 1.0),
            tags=["user_input", "human_contact", "high_importance", "novelty"]
        ))
        # IMPORTANT: pass file paths (not in-memory lists)
        count = (cycle_count or {}).get("count", 0)
        summarize_chat_to_long_memory(count, CHAT_LOG_FILE, LONG_MEMORY_FILE)

    if not raw_signals:
        boredom_prompt = random.choice([
            "There’s been no input lately. Should I reflect, dream, or create something new?",
            "Silence again. What internal need should I act on?",
            "I'm alone with my thoughts. How should I use this time?"
        ])
        raw_signals.append(create_signal(
            source="internal",
            content=boredom_prompt,
            signal_strength=0.3,
            tags=["no_input", "internal_thought", "boredom"]
        ))

    try:
        txt_errors = read_recent_errors_txt(ERROR_FILE, max_lines=5) or []
        for e in txt_errors:
            raw_signals.append(create_signal(
                source="system",
                content=e.strip(),
                signal_strength=0.4,
                tags=["error", "pain", "system"]
            ))

        json_errors = read_recent_errors_json(MODEL_FAILURES_JSON, max_items=5) or []
        for err in json_errors:
            msg = (err or {}).get("error", "Unknown model failure.")
            raw_signals.append(create_signal(
                source="system",
                content=str(msg).strip(),
                signal_strength=0.4,
                tags=["error", "pain", "model"]
            ))
    except Exception as e:
        raw_signals.append(create_signal(
            source="self_monitoring",
            content=f"⚠️ Failed to read error files: {e}",
            signal_strength=0.3,
            tags=["internal", "monitoring"]
        ))

    signals = []
    for signal in raw_signals:
        content = signal.get("content", "")
        if check_violates_boundaries(content):
            if callable(context.get("update_working_memory")):
                context["update_working_memory"]({
                    "content": "⚠️ Input violated boundaries. Skipped.",
                    "event_type": "system",
                    "importance": 2,
                    "priority": 2
                })
            continue
        signals.append(signal)

    # If any signal made it through, update last-active once
    if signals:
        update_last_active()

    # Use a list (JSON-safe) instead of a set if this might be serialized later
    context["_logged_system_signals"] = []

    return signals, context