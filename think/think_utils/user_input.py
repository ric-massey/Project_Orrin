from datetime import datetime, timezone
from utils.knowledge_utils import recall_relevant_knowledge
from utils.generate_response import generate_response
from utils.memory_utils import format_memories_for_prompt
from utils.timing import update_last_active
from emotion.reward_signals.reward_signals import release_reward_signal
from memory.chat_log import log_raw_user_input, get_user_input, summarize_chat_to_long_memory
from utils.log import read_recent_errors_txt, read_recent_errors_json
from cognition.selfhood.boundary_check import check_violates_boundaries
from cognition.selfhood.relationships import summarize_relationships
import random
from paths import ERROR_FILE, CHAT_LOG_FILE

def log_user_input_once(user_input, context):
    if not user_input or not user_input.strip():
        return
    stripped = user_input.strip()
    if stripped in {"—", "-", "--", "---"}:
        return
    last_logged = context.get("last_logged_user_input", "")
    if stripped == last_logged.strip():
        return
    context["last_logged_user_input"] = stripped
    log_raw_user_input(stripped)

def is_real_user_input(user_input):
    if not user_input:
        return False
    test = user_input.strip()
    if not test or test in {"—", "-", "--", "---"}:
        return False
    return True

def handle_user_input(
    context,
    cycle_count,
    long_memory,
    working_memory,
    relationships,
    speaker=None
):
    user_input = get_user_input()
    context["latest_user_input"] = user_input

    # Log user input once here, before any processing
    log_user_input_once(user_input, context)

    raw_signals = []

    user_id = context.get("user_id", "user")
    rel_data = relationships.get(user_id, {
        "influence_score": 0.5,
        "recent_emotional_effect": "neutral"
    })
    influence = rel_data.get("influence_score", 0.5)
    emotional_effect = rel_data.get("recent_emotional_effect", "")

    curiosity = context.get("emotional_state", {}).get("curiosity", 0.5)
    dynamic_signal_strength = round(0.3 + 0.4 * curiosity + 0.2 * influence, 3)

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
        raw_signals.append({
            "source": "user_input",
            "content": user_input,
            "signal_strength": min(dynamic_signal_strength, 1.0),
            "tags": ["user_input", "human_contact", "high_importance", "novelty"]
        })
        summarize_chat_to_long_memory(cycle_count["count"], CHAT_LOG_FILE, long_memory)

    if not raw_signals:
        boredom_prompt = random.choice([
            "There’s been no input lately. Should I reflect, dream, or create something new?",
            "Silence again. What internal need should I act on?",
            "I'm alone with my thoughts. How should I use this time?"
        ])
        raw_signals.append({
            "source": "internal",
            "content": boredom_prompt,
            "signal_strength": 0.3,
            "tags": ["no_input", "internal_thought", "boredom"]
        })

    try:
        txt_errors = read_recent_errors_txt(ERROR_FILE, max_lines=5)
        for e in txt_errors:
            raw_signals.append({
                "source": "system",
                "content": e.strip(),
                "signal_strength": 0.4,
                "tags": ["error", "pain", "system"]
            })

        json_errors = read_recent_errors_json("logs/model_failures.json", max_items=5)
        for err in json_errors:
            msg = err.get("error", "Unknown model failure.")
            raw_signals.append({
                "source": "system",
                "content": msg.strip(),
                "signal_strength": 0.4,
                "tags": ["error", "pain", "model"]
            })
    except Exception as e:
        raw_signals.append({
            "source": "self_monitoring",
            "content": f"⚠️ Failed to read error files: {e}",
            "signal_strength": 0.3,
            "tags": ["internal", "monitoring"]
        })

    # === UPGRADE 1: Avoid setting speech_done if nothing spoken ===
    signals = []
    for signal in raw_signals:
        content = signal.get("content", "")
        if check_violates_boundaries(content):
            if callable(context.get("update_working_memory")):
                context["update_working_memory"]({
                    "content": "⚠️ Input violated boundaries. Skipped.",
                    "event_type": "system",
                    "importance": 2,
                    "priority": 2,
                })
            continue

        if signal["source"] == "user_input":
            relevant_knowledge = recall_relevant_knowledge(content, long_memory=long_memory, working_memory=working_memory, max_items=8)
            for mem in relevant_knowledge:
                if not isinstance(mem, dict):
                    continue
                mem["referenced"] = mem.get("referenced", 0) + 1
                mem["recall_count"] = mem.get("recall_count", 0) + 1

            tone_modifier = ""
            if emotional_effect == "appreciation":
                tone_modifier = "Respond warmly and supportively."
            elif emotional_effect == "hostility":
                tone_modifier = "Respond cautiously and avoid escalation."
            elif influence < 0.2:
                tone_modifier = "Keep response minimal and emotionally distant."

            prompt = (
                f"{tone_modifier}\n\n"
                f"User said: {content}\n"
                f"Top relevant memories:\n{format_memories_for_prompt(relevant_knowledge)}\n"
                f"Relationships: {summarize_relationships(relationships)}"
            )

            response = generate_response(prompt)
            spoken = None

            if response and speaker:
                spoken = speaker.should_speak(response, context.get("emotional_state", {}), context)
                if spoken:
                    if callable(context.get("update_working_memory")):
                        context["update_working_memory"]({
                            "content": spoken,
                            "event_type": "response",
                            "importance": 2,
                            "priority": 2,
                            "referenced": 1
                        })
                    release_reward_signal(
                        context,
                        signal_type="dopamine",
                        actual_reward=0.5,
                        expected_reward=0.4,
                        effort=0.3,
                        mode="phasic",
                        source="spoken_response"
                    )
                    response = None
                    # Only set speech_done if something was actually spoken!
                    context["speech_done"] = True

        else:
            # === UPGRADE 2: Only log unique system/internal signals per cycle ===
            logged_signals = context.setdefault("_logged_system_signals", set())
            log_key = f"{signal['source']}::{content[:60]}"
            if log_key not in logged_signals:
                log_raw_user_input({
                    "user": user_input or "—",
                    "orrin": "(no reply)",
                    "influence": influence,
                    "emotional_effect": emotional_effect,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                logged_signals.add(log_key)

        update_last_active()
        signals.append(signal)

    # Clear unique signal cache for next cycle
    context["_logged_system_signals"] = set()
    return signals, context