# === Standard Library ===
import json
from datetime import datetime, timezone

from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json, save_json
from utils.log import log_error
from memory.working_memory import update_working_memory
from utils.self_model import get_self_model
from paths import (
    LONG_MEMORY_FILE,
)

def evaluate_new_abstractions():
    try:
        # === Load context safely ===
        tools = load_json("proposed_tools.json", default_type=list)
        if not isinstance(tools, list):
            log_error("❌ proposed_tools.json is not a list. Resetting to empty list.")
            tools = []

        if not tools:
            update_working_memory("⚠️ No proposed tools to evaluate.")
            return "❌ No tools found."

        self_model = get_self_model()
        if not isinstance(self_model, dict):
            log_error("❌ self_model is not a dict. Aborting tool evaluation.")
            return "❌ Invalid self model."

        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        if not isinstance(long_memory, list):
            log_error("❌ LONG_MEMORY_FILE is not a list. Using empty long memory.")
            long_memory = []

        evaluations = []

        for tool in tools:
            prompt = (
                "I am Orrin, a reflective AI evaluating a new tool.\n\n"
                f"My core directive is:\n\"{self_model.get('core_directive', {}).get('statement', 'No directive found.')}\"\n\n"
                f"My motivations:\n{json.dumps(self_model.get('core_directive', {}).get('motivations', []), indent=2)}\n\n"
                f"Tool proposed:\n{json.dumps(tool, indent=2)}\n\n"
                f"My relevant long-term memory:\n{json.dumps(long_memory[-10:], indent=2)}\n\n"
                "Evaluate this tool:\n"
                "- Is it original?\n"
                "- Is it useful for fulfilling my directive?\n"
                "- Are there similar tools I already use?\n"
                "- Should I refine, implement, or reject it?\n\n"
                "Respond in JSON:\n"
                "{ \"evaluation\": \"...\", \"action\": \"implement | refine | reject\", \"justification\": \"...\" }"
            )

            response = generate_response(prompt, config={"model": get_thinking_model()})
            eval_result = extract_json(response)

            if eval_result and isinstance(eval_result, dict):
                evaluations.append({
                    "tool": tool,
                    "evaluation": eval_result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                update_working_memory(f"🧠 Evaluated tool: {tool.get('name', '[unnamed]')} — {eval_result.get('action', 'unknown')}")
            else:
                update_working_memory(f"❌ Failed to parse evaluation for tool: {tool.get('name', '[unnamed]')}")

        save_json("tool_evaluations.json", evaluations)
        return f"✅ Evaluated {len(evaluations)} tool(s)."

    except Exception as e:
        log_error(f"evaluate_new_abstractions ERROR: {e}")
        return "❌ Tool evaluation failed."