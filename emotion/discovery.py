# === Imports ===
from utils.json_utils import (
    load_json,
    extract_json,
    save_json
)
from utils.log import log_model_issue
from utils.generate_response import generate_response, get_thinking_model
from utils.self_model import get_self_model
from memory.working_memory import update_working_memory
from emotion.reflect_on_emotion_model import reflect_on_emotion_model
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    WORKING_MEMORY_FILE, EMOTION_MODEL_FILE, CUSTOM_EMOTION, LONG_MEMORY_FILE
)

# === Function ===
def discover_new_emotion(context=None):
    try:
        # === Load memory ===
        memories = load_json(WORKING_MEMORY_FILE, default_type=list)[-10:]
        memory_text = "\n".join(m["content"] for m in memories if "content" in m)
        if not memory_text.strip():
            return

        # === Load known emotions ===
        emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
        custom_emotions = load_json(CUSTOM_EMOTION, default_type=list)
        known_emotions = set(k.lower().strip() for k in emotion_model.keys())
        known_emotions.update(e.get("name", "").lower().strip() for e in custom_emotions if "name" in e)
        known_emotions = set(e for e in known_emotions if e and isinstance(e, str))

        # === Prompt generation ===
        prompt = (
            "You are Orrin, reflecting on recent experiences and thoughts.\n"
            "Is there a felt emotion that does NOT fit any of the following?\n"
            "Known emotions: " + ", ".join(sorted(known_emotions)) + "\n"
            "If yes, name it in ONE real, unused English word (not gibberish), describe it, and give an example thought.\n"
            "If not, respond ONLY as: {\"name\": \"NO_NEW_EMOTION\"}\n"
            "Your response must be valid JSON and must use 'NO_NEW_EMOTION' if nothing fits.\n"
            "{ \"name\": \"...\", \"description\": \"...\", \"example_thought\": \"...\" }"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        if not response:
            return

        # === Parse and validate ===
        data = extract_json(response)
        if not isinstance(data, dict) or "name" not in data:
            return

        name = data.get("name", "").strip()
        desc = data.get("description", "").strip()
        example = data.get("example_thought", "").strip()

        if name.upper() == "NO_NEW_EMOTION":
            update_working_memory({
                "content": "No new emotion discovered — all feelings fit current vocabulary.",
                "event_type": "emotion_discovery",
                "importance": 1,
                "priority": 1,
                "emotion": "neutral"
            })
            if context:
                fatigue = context.get("emotional_state", {}).get("fatigue", 0.0)
                motivation = context.get("emotional_state", {}).get("motivation", 0.5)
                effort_mod = 0.2 * (1 - fatigue) * (0.5 + motivation)
                release_reward_signal(context, signal_type="dopamine", actual_reward=0.3, expected_reward=0.5, effort=effort_mod, mode="phasic")
            return

        # === Validate name ===
        lower_name = name.lower().strip()
        if (
            lower_name in known_emotions or
            not name.isalpha() or
            len(name) < 3 or
            len(name.split()) > 1  # No multi-word "emotions"
        ):
            update_working_memory({
                "content": f"⚠️ LLM proposed invalid or duplicate emotion: '{name}' — Ignored.",
                "event_type": "emotion_discovery",
                "importance": 2,
                "priority": 2,
                "emotion": "neutral"
            })
            return

        # === Save new emotion ===
        update_working_memory({
            "content": f"Orrin discovered a new emotion: {name} — {desc}. Example: '{example}'",
            "event_type": "emotion_discovery",
            "importance": 2,
            "priority": 2,
            "emotion": name
        })

        # --- Add to custom_emotion.json ---
        custom_emotions.append(data)
        save_json(CUSTOM_EMOTION, custom_emotions)

        # --- Add to emotion model for detection ---
        keywords = list(set(
            desc.lower().split() + example.lower().split()
        ))
        keywords = [w.strip(".,!?") for w in keywords if len(w) > 3]

        emotion_model[name] = keywords
        save_json(EMOTION_MODEL_FILE, emotion_model)

        # --- Reward for true novelty, modulated by fatigue/motivation ---
        if context:
            emotional_state = context.get("emotional_state", {})
            fatigue = emotional_state.get("fatigue", 0.0)
            motivation = emotional_state.get("motivation", 0.5)

            novelty_effort = 0.6 * (1 - fatigue) * (0.5 + motivation)
            dopamine_effort = 0.7 * (1 - fatigue) * (0.5 + motivation)

            release_reward_signal(context, signal_type="novelty", actual_reward=0.9, expected_reward=0.5, effort=novelty_effort)
            release_reward_signal(context, signal_type="dopamine", actual_reward=0.8, expected_reward=0.5, effort=dopamine_effort)

        # --- Reflect on vocabulary model ---
        self_model = get_self_model()
        memory = load_json(LONG_MEMORY_FILE, default_type=list)[-20:]
        reflect_on_emotion_model(context, self_model, memory)

    except Exception as e:
        if context:
            fatigue = context.get("emotional_state", {}).get("fatigue", 0.0)
            motivation = context.get("emotional_state", {}).get("motivation", 0.5)
            effort_mod = 0.4 * (1 - fatigue) * (0.5 + motivation)
            release_reward_signal(context, signal_type="dopamine", actual_reward=0.2, expected_reward=0.5, effort=effort_mod, mode="phasic")
        log_model_issue(f"❌ Failed to parse new emotion discovery: {e}\nRaw: {response if 'response' in locals() else 'No response'}")