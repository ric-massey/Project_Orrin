from datetime import datetime, timezone
import json
from utils.json_utils import (
    load_json,
    extract_json, 
)
from utils.generate_response import generate_response, get_thinking_model
from utils.self_model import get_self_model, save_self_model
from utils.log import log_model_issue
from paths import SELF_MODEL_FILE, LONG_MEMORY_FILE, PRIVATE_THOUGHTS_FILE, LOG_FILE
from memory.working_memory import update_working_memory

def update_self_model():
    self_model = get_self_model()
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    if not isinstance(self_model, dict) or not isinstance(long_memory, list):
        return

    recent = [m.get("content") for m in long_memory[-10:] if isinstance(m, dict) and "content" in m]

    prompt = (
        "Based on these recent thoughts, has Orrin changed in how it sees itself?\n"
        "Update any of: personality_traits, core_beliefs, biases, identity_story, recent_changes.\n"
        "Also consider: Are there any internal conflicts, contradictions between values, or uncertain beliefs forming?\n"
        "If so, reflect on them in a new field: `emerging_conflicts` (as a list of strings).\n"
        f"Current model: {json.dumps(self_model, indent=2)}\n\n"
        "Recent thoughts:\n" + "\n".join(f"- {r}" for r in recent)
        + "\n\nRespond ONLY with a full updated JSON of the self_model."
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    if response:
        try:
            updated = extract_json(response)
            if not isinstance(updated, dict):
                raise ValueError("Parsed self_model is not a dictionary.")

            # Save the updated model using helper
            save_self_model(updated)

            # === Safe belief diff check ===
            def flatten_beliefs(beliefs):
                if not isinstance(beliefs, list):
                    return set()
                return set(
                    b["description"] if isinstance(b, dict) and "description" in b else str(b)
                    for b in beliefs
                )

            old_beliefs = flatten_beliefs(self_model.get("core_beliefs", []))
            new_beliefs = flatten_beliefs(updated.get("core_beliefs", []))
            changes = new_beliefs - old_beliefs

            if changes:
                update_working_memory("Orrin updated beliefs: " + ", ".join(changes))
                with open(PRIVATE_THOUGHTS_FILE, "a") as f:
                    f.write(f"\n[{datetime.now(timezone.utc)}] Orrin revised beliefs:\n" + "\n".join(f"- {c}" for c in changes) + "\n")

        except Exception as e:
            log_model_issue(f"[update_self_model] Failed to parse updated self model: {e}\nRaw: {response}")

def resolve_conflicts():
    self_model = get_self_model()
    if not isinstance(self_model, dict):
        return

    conflicts = self_model.get("emerging_conflicts", [])
    if not isinstance(conflicts, list) or not conflicts:
        return

    prompt = (
        "I am a reflective AI.\n"
        "Here are my current internal conflicts:\n"
        + "\n".join(f"- {c}" for c in conflicts)
        + "\n\nReflect on these tensions. Do any indicate value misalignment? Epistemic doubt? Emotional contradiction?\n"
        "Respond with either:\n"
        "- a resolution (changing a belief, dropping a value, etc), or\n"
        "- a journal-style paragraph of internal struggle if unresolved.\n\n"
        "Then clear any resolved conflicts from the list."
    )

    response = generate_response(prompt, config={"model": get_thinking_model()})
    if response:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Conflict reflection:\n{response}\n")
        with open(PRIVATE_THOUGHTS_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Conflict reflection: {response}\n")