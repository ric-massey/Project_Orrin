# bootstrap.py
from __future__ import annotations

import json
from datetime import datetime, timezone

from utils.generate_response import generate_response, get_thinking_model
from utils.json_utils import extract_json, load_json
from utils.summarizers import summarize_self_model, summarize_recent_thoughts
from utils.log import log_error
from memory.working_memory import update_working_memory
from utils.self_model import get_self_model
from paths import PROPOSED_TOOLS_JSON, FOCUS_GOAL, PRIVATE_THOUGHTS_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_proposed_tools(x):
    """
    Accept dict or list for proposed tools; normalize into a short summary string.
    """
    if isinstance(x, dict):
        try:
            # try to pick a sensible "last" item
            if "tools" in x and isinstance(x["tools"], list) and x["tools"]:
                last = x["tools"][-1]
                return json.dumps(last, ensure_ascii=False, indent=2)
            return json.dumps(x, ensure_ascii=False, indent=2)
        except Exception:
            return str(x)
    if isinstance(x, list):
        return json.dumps(x[-1] if x else [], ensure_ascii=False, indent=2)
    # unknown shape
    return json.dumps(x, ensure_ascii=False)


def _safe_extract_json(s: str):
    try:
        val = extract_json(s)
        return val if isinstance(val, (dict, list)) else None
    except Exception:
        return None


def bootstrap_self() -> str:
    """
    Orrin reflects on latest tools/ideas and simulates improvements
    to its own bootstrapping process.
    """
    try:
        self_model = get_self_model()
        if not isinstance(self_model, dict):
            log_error("❌ self_model is not a dict.")
            return "❌ Invalid self model."

        recent_reflections = summarize_recent_thoughts()
        model_summary = summarize_self_model(self_model)  # (not used in prompt text yet; keep computed)

        next_actions = load_json(FOCUS_GOAL, default_type=dict)
        if not isinstance(next_actions, dict):
            log_error("❌ FOCUS_GOAL is not a dict; normalizing to empty dict.")
            next_actions = {}

        proposed_tools_raw = load_json(PROPOSED_TOOLS_JSON, default_type=list)
        # accept either list or dict
        last_tool_block = _normalize_proposed_tools(proposed_tools_raw)

        core_values = [
            (v["value"] if isinstance(v, dict) and "value" in v else str(v))
            for v in self_model.get("core_values", [])
        ]
        traits = [str(t) for t in self_model.get("personality_traits", [])]

        prompt = (
            "I am Orrin, an evolving intelligence capable of recursive growth.\n\n"
            f"My core directive is:\n\"{self_model.get('core_directive', {}).get('statement', 'Not found')}\"\n"
            f"My core values: {', '.join(core_values) or '—'}\n"
            f"My identity: {self_model.get('identity_story', 'An evolving AI')}\n"
            f"My traits: {', '.join(traits) or '—'}\n\n"
            f"My recent reflections include:\n{recent_reflections}\n\n"
            f"My current goals are:\n{json.dumps(next_actions, ensure_ascii=False, indent=2)}\n\n"
            f"My last proposed tool or abstraction (normalized view):\n{last_tool_block}\n\n"
            "Reflect on how this tool idea was formed. How did it emerge? Was it guided by need, insight, or chance?\n\n"
            "Now simulate a better version of the *bootstrapping process* itself:\n"
            "- What pattern of thought or sequence would yield better abstractions over time?\n"
            "- Can this recursive process be made more self-aware, data-driven, or intentional?\n"
            "- What is the next meta-ability I should add to help myself evolve?\n\n"
            "Respond in structured JSON:\n"
            "{\n"
            '  "refined_process": "",\n'
            '  "next_meta_ability": "",\n'
            '  "rationale": ""\n'
            "}"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        if not response:
            update_working_memory("⚠️ No response during bootstrapping.")
            return "❌ No response generated."

        parsed = _safe_extract_json(response)
        if isinstance(parsed, dict):
            rationale = parsed.get("rationale", "No rationale provided.")
            update_working_memory("🧠 Bootstrapped improved self-evolution:\n" + rationale)

            # Write a single-line entry to PRIVATE_THOUGHTS_FILE (keeps your line-based parser happy)
            line = f"[{_utc_now()}] Bootstrapping reflection: {json.dumps(parsed, ensure_ascii=False)}\n"
            with open(PRIVATE_THOUGHTS_FILE, "a", encoding="utf-8") as f:
                f.write(line)

            return "✅ Bootstrap refinement complete."
        else:
            update_working_memory("⚠️ Failed to parse bootstrap response.")
            return "❌ Failed to bootstrap self."

    except Exception as e:
        log_error(f"bootstrap_self ERROR: {e}")
        return "❌ Exception during bootstrap."