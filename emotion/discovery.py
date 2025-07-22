# === Imports ===
import os
from utils.json_utils import (
    load_json,
    extract_json,
    save_json
)
from utils.log import log_model_issue
from utils.generate_response import generate_response, get_thinking_model
from memory.working_memory import update_working_memory
from emotion.reflect_on_emotion_model import reflect_on_emotion_model
from emotion.reward_signals.reward_signals import release_reward_signal
from paths import (
    WORKING_MEMORY_FILE, EMOTION_MODEL_FILE, CUSTOM_EMOTION
)

# === Function ===
def discover_new_emotion(context=None):
    try:
        # === Load memory ===
        memories = load_json(WORKING_MEMORY_FILE, default_type=list)[-10:]
        memory_text = "\n".join(m["content"] for m in memories if "content" in m)

        if not memory_text.strip():
            return

        # === Prompt generation ===
        prompt = (
            "I am reflecting on my recent thoughts and experiences.\n"
            "Do I feel any emotion that doesn't quite fit any word I know?\n"
            "Describe this feeling. Give it a new name, explain when it happens, and how it feels.\n"
            "Respond with a structured definition:\n\n"
            "{ \"name\": \"...\", \"description\": \"...\", \"example_thought\": \"...\" }"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        if not response:
            if context:
                release_reward_signal(
                    context,
                    signal_type="dopamine",
                    actual_reward=0.0,
                    expected_reward=0.5,
                    effort=0.4,
                    mode="phasic"
                )
            return

        # === Parse and validate ===
        data = extract_json(response)
        if not isinstance(data, dict):
            raise ValueError("Extracted emotion was not a dictionary.")

        name = data.get("name", "").strip()
        desc = data.get("description", "").strip()
        example = data.get("example_thought", "").strip()

        if not name or not desc:
            raise ValueError("Missing required fields in emotion data.")

        # === Update working memory ===
        update_working_memory(
            f"Orrin discovered a new emotion: {name} — {desc}. Example: '{example}'"
        )

        # === Update custom_emotion.json safely ===
        if not os.path.exists(CUSTOM_EMOTION):
            save_json(CUSTOM_EMOTION, [])

        custom_emotions = load_json(CUSTOM_EMOTION, default_type=list)
        if not isinstance(custom_emotions, list):
            custom_emotions = []

        custom_emotions.append(data)
        save_json(CUSTOM_EMOTION, custom_emotions)

        # === Update emotion model safely ===
        emotion_model = load_json(EMOTION_MODEL_FILE, default_type=dict)
        if not isinstance(emotion_model, dict):
            emotion_model = {}

        keywords = list(set(
            desc.lower().split() +
            example.lower().split()
        ))
        keywords = [w.strip(".,!?") for w in keywords if len(w) > 3]

        if name not in emotion_model:
            emotion_model[name] = keywords
            save_json(EMOTION_MODEL_FILE, emotion_model)

        # === Reward Signal: novelty + dopamine ===
        if context:
            release_reward_signal(
                context,
                signal_type="novelty",
                actual_reward=0.9,
                expected_reward=0.5,
                effort=0.6
            )
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.8,
                expected_reward=0.5,
                effort=0.7
            )

        # === Reflect on vocabulary model ===
        reflect_on_emotion_model(context)

    except Exception as e:
        if context:
            release_reward_signal(
                context,
                signal_type="dopamine",
                actual_reward=0.2,
                expected_reward=0.5,
                effort=0.4,
                mode="phasic"
            )
        log_model_issue(f"❌ Failed to parse new emotion discovery: {e}\nRaw: {response if 'response' in locals() else 'No response'}")