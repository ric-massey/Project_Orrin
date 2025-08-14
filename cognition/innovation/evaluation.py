# evaluation.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json, save_json
from utils.log import log_error
from memory.working_memory import update_working_memory
from utils.self_model import get_self_model
from paths import PROPOSED_TOOLS_JSON, TOOL_EVALUATIONS_JSON, LONG_MEMORY_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_extract_json(s: str) -> Dict[str, Any] | None:
    try:
        val = extract_json(s)
        return val if isinstance(val, dict) else None
    except Exception:
        return None


def evaluate_new_abstractions() -> str:
    try:
        # === Load context safely ===
        tools = load_json(PROPOSED_TOOLS_JSON, default_type=list)
        if not isinstance(tools, list):
            update_working_memory("⚠️ proposed_tools.json was not a list; treating as empty.")
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
            update_working_memory("⚠️ LONG_MEMORY_FILE not a list; using empty.")
            long_memory = []

        prior = load_json(TOOL_EVALUATIONS_JSON, default_type=list)
        if not isinstance(prior, list):
            prior = []

        evaluations: List[Dict[str, Any]] = []
        recent_long = long_memory[-10:]

        for tool in tools:
            # Skip junk entries gracefully
            if not isinstance(tool, dict):
                update_working_memory("⚠️ Skipped non-dict tool entry during evaluation.")
                continue

            prompt = (
                "I am Orrin, a reflective AI evaluating a new tool.\n\n"
                f"My core directive is:\n\"{self_model.get('core_directive', {}).get('statement', 'No directive found.')}\"\n\n"
                f"My motivations:\n{json.dumps(self_model.get('core_directive', {}).get('motivations', []), ensure_ascii=False, indent=2)}\n\n"
                f"Tool proposed:\n{json.dumps(tool, ensure_ascii=False, indent=2)}\n\n"
                f"My relevant long-term memory:\n{json.dumps(recent_long, ensure_ascii=False, indent=2)}\n\n"
                "Evaluate this tool:\n"
                "- Is it original?\n"
                "- Is it useful for fulfilling my directive?\n"
                "- Are there similar tools I already use?\n"
                "- Should I refine, implement, or reject it?\n\n"
                "Respond in JSON:\n"
                '{ "evaluation": "", "action": "implement | refine | reject", "justification": "" }'
            )

            resp = generate_response(prompt, config={"model": get_thinking_model()})
            parsed = _safe_extract_json(resp or "")

            name = tool.get("name", "[unnamed]")
            if parsed is not None:
                action = parsed.get("action", "unknown")
                evaluations.append({
                    "tool": tool,
                    "evaluation": parsed,
                    "timestamp": _utc_now(),
                })
                update_working_memory(f"🧠 Evaluated tool: {name} — {action}")
            else:
                update_working_memory(f"❌ Failed to parse evaluation for tool: {name}")

        # Merge with prior evaluations rather than overwriting
        if evaluations:
            save_json(TOOL_EVALUATIONS_JSON, prior + evaluations)

        return f"✅ Evaluated {len(evaluations)} tool(s)."

    except Exception as e:
        log_error(f"evaluate_new_abstractions ERROR: {e}")
        return "❌ Tool evaluation failed."