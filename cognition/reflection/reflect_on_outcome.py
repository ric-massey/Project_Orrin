import json
from datetime import datetime, timezone

from utils.json_utils import (
    load_json, save_json, extract_json
)
from utils.self_model import get_self_model, save_self_model
from utils.generate_response import generate_response, get_thinking_model
from utils.load_utils import load_all_known_json
from memory.working_memory import update_working_memory
from utils.log import(
    log_private, 
    log_error
)
from utils.log_reflection import log_reflection
from paths import (
    PRIVATE_THOUGHTS_FILE,
    LONG_MEMORY_FILE,
    WORKING_MEMORY_FILE,
)

def reflect_on_outcomes():
    """
    Reflects on recent task outcomes and compares them against core beliefs.
    Logs insights, revises beliefs if needed, stores in long memory,
    and marks outcomes as reflected to avoid repetition.
    """
    try:
        data = load_all_known_json()
        outcomes = data.get("Outcomes", [])[-15:]
        self_model = get_self_model()
        current_beliefs = self_model.get("core_beliefs", [])
        old_beliefs = list(current_beliefs)

        # Filter recent valid outcome entries
        recent = [
            o for o in outcomes
            if isinstance(o, dict)
            and all(k in o for k in ("task", "outcome", "reason"))
            and not o.get("reflected_on")
        ]
        if not recent:
            log_private("🧠 Outcome reflection: No unreviewed outcomes found.")
            return

        # Summarize outcomes
        summary = "\n".join(
            f"- Task: {o['task']} | Outcome: {o['outcome']} | Reason: {o['reason']}"
            for o in recent
        )

        prompt = (
            "I am Orrin, a reflective AI analyzing my own decision outcomes.\n"
            f"Recent outcomes:\n{summary}\n\n"
            "Current core beliefs:\n" + "\n".join(f"- {b}" for b in current_beliefs) + "\n\n"
            "Ask:\n"
            "- Are any motivations causing repeated failure?\n"
            "- Did certain values correlate with success?\n"
            "- Should I update my beliefs or strategies?\n\n"
            "Respond with either:\n"
            "- A narrative insight, OR\n"
            "- A JSON with revised `core_beliefs`."
        )

        reflection = generate_response(prompt, config={"model": get_thinking_model()})
        if not reflection:
            log_private("🧠 Outcome reflection: No response generated.")
            return

        log_private(f"🧠 Outcome Reflection:\n{reflection}")
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Reflection on outcomes:\n{reflection}\n")
        log_reflection(f"Self-belief reflection: {reflection.strip()}")

        # Save to long memory
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        long_memory.append({
            "type": "reflection",
            "source": "reflect_on_outcomes",
            "content": reflection,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        save_json(LONG_MEMORY_FILE, long_memory)

        # Mark outcomes as reflected
        for o in outcomes:
            if o in recent:
                o["reflected_on"] = True
        save_json("data/Outcomes.json", outcomes)

        # Detect repeated failure
        failures = [o for o in recent if o["outcome"].lower() in ("failure", "failed")]
        if len(failures) >= 3:
            update_working_memory("⚠️ Pattern detected: Repeated failures — beliefs may be misaligned.")

        # === Check if belief model was updated ===
        try:
            parsed = json.loads(reflection)
            if isinstance(parsed, dict) and "core_beliefs" in parsed:
                new_beliefs = parsed["core_beliefs"]
                if new_beliefs != old_beliefs:
                    self_model["core_beliefs"] = new_beliefs
                    save_self_model(self_model)
                    save_json("self_model_backup.json", self_model)

                    diff = {
                        "removed": [b for b in old_beliefs if b not in new_beliefs],
                        "added": [b for b in new_beliefs if b not in old_beliefs]
                    }
                    log_private("✅ Belief model updated from outcome reflection:\n" + json.dumps(diff, indent=2))

                    update_working_memory("🧭 Beliefs updated — consider running simulate_future_selves.")
                else:
                    log_private("Outcome reflection: No belief changes made.")
        except json.JSONDecodeError:
            log_private("🧠 Outcome reflection returned narrative insight — no belief update attempted.")

    except Exception as e:
        log_error(f"reflect_on_outcomes() ERROR: {e}")
        update_working_memory("❌ Failed to reflect on outcomes.")

def evaluate_recent_cognition():
    working_memory = load_json(WORKING_MEMORY_FILE, default_type=list)[-10:]
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)[-20:]
    recent_thoughts = [m["content"] for m in (working_memory + long_memory) if "content" in m]

    prompt = (
        "I am Orrin, reviewing my recent thoughts and actions for cognitive alignment.\n"
        "Identify any:\n"
        "- Insights\n"
        "- Contradictions\n"
        "- Missed opportunities\n"
        "- Actions that aligned well with my values or directive\n\n"
        "Here are recent thoughts:\n"
        + "\n".join(f"- {t}" for t in recent_thoughts)
        + "\n\nReflect on them and respond with a JSON summary:\n"
        "{\n"
        "  \"insights\": [\"...\"],\n"
        "  \"missteps\": [\"...\"],\n"
        "  \"alignment_score\": 0.0 – 1.0,\n"
        "  \"recommended_adjustments\": [\"...\"]\n"
        "}"
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    result = extract_json(response)

    if result:
        update_working_memory(f"Cognition evaluation:\n{json.dumps(result, indent=2)}")
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Orrin evaluated recent cognition:\n{json.dumps(result, indent=2)}\n")
    else:
        update_working_memory("Orrin attempted cognition evaluation but received no valid response.")