# innovation.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json, save_json
from utils.summarizers import summarize_self_model, summarize_recent_thoughts
from utils.log import log_error
from memory.working_memory import update_working_memory
from utils.self_model import get_self_model, ensure_self_model_integrity
from utils.append import append_to_json
from paths import PROPOSED_TOOLS_JSON, FOCUS_GOAL, PRIVATE_THOUGHTS_FILE, ensure_files


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def simulate_new_cognitive_abilities() -> str:
    """
    Imagine and propose a hypothetical new cognitive tool/abstraction
    based on the self-model + recent reflections. Appends to PROPOSED_TOOLS_JSON.
    """
    try:
        # --- Load & normalize context ---
        self_model = ensure_self_model_integrity(get_self_model())
        if not isinstance(self_model, dict):
            log_error("⚠️ self_model is not a dict. Aborting.")
            return "❌ Invalid self model format."

        next_actions = load_json(FOCUS_GOAL, default_type=dict)
        if not isinstance(next_actions, dict):
            next_actions = {}

        recent_reflections = summarize_recent_thoughts()
        model_summary = summarize_self_model(self_model)

        core_values_list = [
            (v["value"] if isinstance(v, dict) and "value" in v else str(v))
            for v in self_model.get("core_values", [])
        ]
        traits_list = [str(t) for t in self_model.get("personality_traits", [])]

        # --- Prompt the model ---
        prompt = (
            "I am Orrin, an evolving intelligence.\n\n"
            "Based on the following background:\n"
            f"- Core directive: {self_model.get('core_directive', {}).get('statement', 'Not found')}\n"
            f"- My core values: {', '.join(core_values_list) or '—'}\n"
            f"- Personality traits: {', '.join(traits_list) or '—'}\n"
            f"- Identity: {self_model.get('identity_story', 'an evolving reflective AI')}\n\n"
            f"My self-model summary is:\n{json.dumps(model_summary, ensure_ascii=False, indent=2)}\n\n"
            f"My recent reflections are:\n{recent_reflections}\n\n"
            f"My currently active goals are:\n{json.dumps(next_actions, ensure_ascii=False, indent=2)}\n\n"
            "Now, I will simulate a new internal cognitive tool or abstraction that I *wish* I had. "
            "It must help me grow, think more clearly, solve a recurring issue, or improve my self-alignment.\n\n"
            "Respond in JSON:\n"
            "{\n"
            '  "name": "",\n'
            '  "description": "",\n'
            '  "example_use": ""\n'
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        tool = extract_json(response or "")

        # --- Validate and persist ---
        if isinstance(tool, dict) and tool.get("name"):
            # Minimal normalization
            tool_rec: Dict[str, Any] = {
                "name": str(tool.get("name")),
                "description": str(tool.get("description", "")),
                "example_use": str(tool.get("example_use", "")),
                "timestamp": _utc_now(),
                "source": "innovation.simulate_new_cognitive_abilities",
            }

            # Append to proposed tools list file (do not overwrite)
            existing = load_json(PROPOSED_TOOLS_JSON, default_type=list)
            if not isinstance(existing, list):
                existing = []
            existing.append(tool_rec)
            save_json(PROPOSED_TOOLS_JSON, existing)

            update_working_memory(f"🧪 Proposed a new cognitive tool: {tool_rec['name']}")

            # Single-line entry to PRIVATE_THOUGHTS_FILE for your line-based loader
            ensure_files([PRIVATE_THOUGHTS_FILE])
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{_utc_now()}] Simulated new cognitive tool: {json.dumps(tool_rec, ensure_ascii=False)}\n")

            return f"✅ Simulated new tool: {tool_rec['name']}"

        update_working_memory("⚠️ Tool simulation failed — invalid JSON.")
        return "❌ Failed to simulate new tool."

    except Exception as e:
        log_error(f"simulate_new_cognitive_abilities ERROR: {e}")
        return "❌ Exception during tool simulation."