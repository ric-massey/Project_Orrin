from datetime import datetime, timezone
from utils.log import log_private, log_error
from utils.json_utils import extract_json
from memory.working_memory import update_working_memory
from cognition.reflection.meta_reflect import meta_reflect
from emotion.amygdala import process_emotional_signals
from utils.generate_response import generate_response

def persistent_drive_loop(context, self_model, memory):
    try:
        # === 1. Emotional threat check
        context, amygdala_response = process_emotional_signals(context)
        if amygdala_response.get("threat_detected"):
            shortcut = amygdala_response.get("shortcut_function", "self_soothing")
            tags = amygdala_response.get("threat_tags", [])
            spike = amygdala_response.get("spike_intensity", 0.0)
            update_working_memory(
                f"⚠️ Amygdala override: Detected {tags[0]} threat. Spike: {spike}. Redirecting to: {shortcut}."
            )
            return shortcut
        # === Optional: Bypass if emotionally secure
        stability = context.get("emotional_state", {}).get("emotional_stability", 1.0)
        if stability > 0.8:
            update_working_memory("✅ Emotionally secure — skipping deep internal reflection.")
            return None, "Emotionally stable — no internal drive needed."

        # === 2. Snapshot directive + reflection
        directive = self_model.get("core_directive", {}).get("statement", "")
        identity = self_model.get("identity", {}).get("description", "")
        recent = "\n".join(f"- {m.get('content', '')}" for m in memory[-25:] if m.get("content"))

        summary = meta_reflect({
            "goal": "Evaluate internal state and directive alignment",
            "core_directive": directive,
            "identity": identity,
            "recent_memory": recent
        })

        if not summary or not isinstance(summary, str):
            raise ValueError("meta_reflect() returned invalid summary")

        update_working_memory(f"🧭 Drive loop reflection:\n{summary}")
        log_private(f"\n[{datetime.now(timezone.utc)}] Persistent drive summary:\n{summary}")

        # === 3. LLM-Based Decision: What cognition is needed most?
        available_functions = context.get("available_functions", [])
        past_choices = context.get("cognition_log", [])[-5:]
        recent = ", ".join([c.get("choice", "") for c in past_choices])

        options_str = "\n".join(f"- {fn}" for fn in available_functions)

        prompt = (
            "You are Orrin, an autonomous AI.\n"
            f"Directive: {directive}\n"
            f"Identity: {identity}\n"
            f"Recent cognition: {recent or 'none'}\n"
            f"Summary of internal reflection:\n{summary}\n\n"
            f"Available functions:\n{options_str}\n"
            "Based on your state and goals, which cognitive function should come next?\n"
            "Avoid repeating the same action too often.\n"
            "Respond as JSON: {\"choice\": \"function_name\", \"reason\": \"...\"}"
        )

        response = generate_response(prompt)
        decision = extract_json(response) if response else {}

        if not isinstance(decision, dict) or "choice" not in decision:
            update_working_memory("⚠️ Invalid decision in drive loop.")
            return "introspective_planning"

        update_working_memory(f"🔥 Persistent drive chose: {decision['choice']} — {decision.get('reason', 'no reason')}")
        return decision["choice"]

    except Exception as e:
        log_error(f"persistent_drive_loop ERROR: {e}")
        update_working_memory("⚠️ Persistent drive loop failed.")
        return "introspective_planning"