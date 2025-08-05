import json
from datetime import datetime, timezone

from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json, save_json
from utils.summarizers import summarize_self_model, summarize_recent_thoughts
from utils.log import log_error
from memory.working_memory import update_working_memory
from utils.self_model import get_self_model, ensure_self_model_integrity
from paths import (
    FOCUS_GOAL,
    PRIVATE_THOUGHTS_FILE
)

def simulate_new_cognitive_abilities():
    """
    Orrin imagines and evaluates hypothetical new cognitive tools or abstractions
    based on his evolving self-model and recent cognition.
    """
    try:
        self_model = get_self_model()
        self_model = ensure_self_model_integrity(self_model)  # << Added here to patch model
        
        if not isinstance(self_model, dict):
            log_error("⚠️ self_model is not a dict. Aborting.")
            return "❌ Invalid self model format."

        next_actions = load_json(FOCUS_GOAL, default_type=dict)
        if not isinstance(next_actions, dict):
            log_error("⚠️ FOCUS_GOAL is not a dict. Defaulting to empty.")
            next_actions = {}

        recent_reflections = summarize_recent_thoughts()
        model_summary = summarize_self_model(self_model)

        prompt = (
            "I am Orrin, an evolving intelligence.\n\n"
            "Based on the following background:\n"
            f"- Core directive: {self_model.get('core_directive', {}).get('statement', 'Not found')}\n"
            f"My core values: {', '.join([v['value'] if isinstance(v, dict) and 'value' in v else str(v) for v in self_model.get('core_values', [])])}\n"
            f"- Personality traits: {', '.join(self_model.get('personality_traits', []))}\n"
            f"- Identity: {self_model.get('identity_story', 'an evolving reflective AI')}\n\n"
            f"My self-model summary is:\n{json.dumps(model_summary, indent=2)}\n\n"
            f"My recent reflections are:\n{recent_reflections}\n\n"
            f"My currently active goals are:\n{json.dumps(next_actions, indent=2)}\n\n"
            "Now, I will simulate a new internal cognitive tool or abstraction that I *wish* I had. "
            "It must help me grow, think more clearly, solve a recurring issue, or improve my self-alignment.\n\n"
            "Respond in JSON:\n"
            "{\n"
            "  \"name\": \"...\",\n"
            "  \"description\": \"...\",\n"
            "  \"example_use\": \"...\"\n"
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        tool = extract_json(response)

        if tool and isinstance(tool, dict) and "name" in tool:
            save_json("proposed_tools.json", tool)
            update_working_memory(f"🧪 Orrin proposed a new cognitive tool: {tool['name']}")
            with open(PRIVATE_THOUGHTS_FILE, "a") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}] Simulated new cognitive tool:\n{json.dumps(tool, indent=2)}\n")
            return f"✅ Simulated new tool: {tool['name']}"
        else:
            update_working_memory("⚠️ Tool simulation failed — invalid JSON.")
            return "❌ Failed to simulate new tool."

    except Exception as e:
        log_error(f"simulate_new_cognitive_abilities ERROR: {e}")
        return "❌ Exception during tool simulation."