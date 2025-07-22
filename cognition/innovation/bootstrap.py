# === Standard Library ===
import json
from datetime import datetime, timezone

# === Internal Utilities ===
from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json
from utils.summarizers import summarize_self_model, summarize_recent_thoughts
from utils.log import log_error
from memory.working_memory import update_working_memory
from utils.self_model import get_self_model, save_self_model  # <-- Use helpers!
from paths import (
    FOCUS_GOAL,
    PRIVATE_THOUGHTS_FILE
)

def bootstrap_self():
    """
    Orrin reflects on his latest self-generated tools or ideas,
    and simulates improvements to his own bootstrapping process.
    """
    try:
        self_model = get_self_model()
        if not isinstance(self_model, dict):
            log_error("❌ self_model is not a dict.")
            return "❌ Invalid self model."

        recent_reflections = summarize_recent_thoughts()
        model_summary = summarize_self_model(self_model)

        next_actions = load_json(FOCUS_GOAL, default_type=dict)
        if not isinstance(next_actions, dict):
            log_error("❌ FOCUS_GOAL is not a dict.")
            next_actions = {}

        tool_history = load_json("proposed_tools.json", default_type=dict)
        if not isinstance(tool_history, dict):
            log_error("❌ proposed_tools.json is not a dict.")
            tool_history = {}

        prompt = (
            "I am Orrin, an evolving intelligence capable of recursive growth.\n\n"
            f"My core directive is:\n\"{self_model.get('core_directive', {}).get('statement', 'Not found')}\"\n"
            f"My core values: {', '.join([v['value'] if isinstance(v, dict) and 'value' in v else str(v) for v in self_model.get('core_values', [])])}\n"
            f"My identity: {self_model.get('identity_story', 'An evolving AI')}\n"
            f"My traits: {', '.join(self_model.get('personality_traits', []))}\n\n"
            f"My recent reflections include:\n{recent_reflections}\n\n"
            f"My current goals are:\n{json.dumps(next_actions, indent=2)}\n\n"
            f"My last proposed tool or abstraction:\n{json.dumps(tool_history, indent=2)}\n\n"
            "Reflect on how this tool idea was formed. How did it emerge? Was it guided by need, insight, or chance?\n\n"
            "Now simulate a better version of the *bootstrapping process* itself:\n"
            "- What pattern of thought or sequence would yield better abstractions over time?\n"
            "- Can this recursive process be made more self-aware, data-driven, or intentional?\n"
            "- What is the next meta-ability I should add to help myself evolve?\n\n"
            "Respond in structured JSON:\n"
            "{\n"
            "  \"refined_process\": \"...\",\n"
            "  \"next_meta_ability\": \"...\",\n"
            "  \"rationale\": \"...\"\n"
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        if not response:
            update_working_memory("⚠️ No response during bootstrapping.")
            return "❌ No response generated."

        result = extract_json(response)

        if result and isinstance(result, dict):
            rationale = result.get("rationale", "No rationale provided.")
            update_working_memory("🧠 Bootstrapped improved self-evolution:\n" + rationale)
            with open(PRIVATE_THOUGHTS_FILE, "a") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}] Bootstrapping reflection:\n{json.dumps(result, indent=2)}\n")
            return "✅ Bootstrap refinement complete."
        else:
            update_working_memory("⚠️ Failed to parse bootstrap response.")
            return "❌ Failed to bootstrap self."

    except Exception as e:
        log_error(f"bootstrap_self ERROR: {e}")
        return "❌ Exception during bootstrap."