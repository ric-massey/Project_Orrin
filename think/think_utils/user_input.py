from datetime import datetime, timezone
from utils.knowledge_utils import recall_relevant_knowledge
from utils.generate_response import generate_response
from utils.memory_utils import summarize_memories
from utils.timing import update_last_active
from emotion.reward_signals.reward_signals import release_reward_signal
from memory.chat_log import log_raw_user_input, get_user_input, summarize_chat_to_long_memory
from memory.working_memory import update_working_memory
from utils.log import read_recent_errors_txt, read_recent_errors_json
from selfhood.boundary_check import check_violates_boundaries
from selfhood.relationships import summarize_relationships
import random
from paths import ERROR_FILE

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

    # --- If real input exists, log and process it ---
    if user_input:
        release_reward_signal(
            context,
            signal_type="connection",
            actual_reward=1.0,
            expected_reward=0.4,
            effort=0.2,
            mode="phasic"
        )

        raw_signals.append({
            "source": "user_input",
            "content": user_input,
            "signal_strength": min(dynamic_signal_strength, 1.0),
            "tags": ["user_input", "human_contact", "high_importance", "novelty"]
        })

        summarize_chat_to_long_memory(cycle_count["count"], "memory/chat_log.json", long_memory)

    # --- If no input, simulate internal boredom signal ---
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

    # --- Add system/model errors as pain signals ---
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

    # === Process all signals ===
    signals = []
    for signal in raw_signals:
        content = signal.get("content", "")
        if check_violates_boundaries(content):
            update_working_memory("⚠️ Input violated boundaries. Skipped.")
            continue

        knowledge = recall_relevant_knowledge(content, max_items=3)
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
            f"Relevant memories: {summarize_memories(long_memory + working_memory)}\n"
            f"Relevant knowledge:\n{'; '.join(knowledge)}\n"
            f"Relationships: {summarize_relationships(relationships)}"
        )

        response = generate_response(prompt)
        spoken = None

        if response and speaker:
            spoken = speaker.should_speak(response, context.get("emotional_state", {}), context)
            if spoken:
                update_working_memory(spoken)
                response = None

        log_raw_user_input({
            "user": user_input or "—",
            "orrin": spoken or response or "(no reply)",
            "influence": influence,
            "emotional_effect": emotional_effect,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        context["speech_done"] = True
        update_last_active()
        signals.append(signal)

    return signals, context