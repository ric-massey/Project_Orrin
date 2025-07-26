from datetime import datetime, timezone

from cognition.reflection.meta_reflect import meta_reflect
from utils.code_validation import validate_think_code
from memory.working_memory import update_working_memory
from utils.json_utils import load_json
from utils.log import log_error, log_private
from utils.generate_response import generate_response, get_thinking_model
from utils.summarizers import summarize_recent_thoughts
from utils.self_model import get_self_model, save_self_model  # <- import helpers

from paths import (
    SELF_MODEL_FILE,
    LONG_MEMORY_FILE,
    CORE_MEMORY_FILE,
)

THINK_MODULE = "cognition/think_module.py"
THINK_BACKUP = "cognition/think_module_backup.py"


def revise_think():
    """
    Allows Orrin to reflectively rewrite its core think() function
    using recent thoughts, internal state, and past results.
    """
    try:
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        self_model = get_self_model()  # <- USE HELPER

        # === Load current think() code ===
        try:
            with open(THINK_MODULE, "r") as f:
                old_code = f.read()
        except FileNotFoundError:
            log_error("think_module.py not found.")
            return "❌ think_module.py not found."

        # === Reflect on why revision is needed ===
        reason_for_revision = meta_reflect({
            "goal": "Improve my own thinking process",
            "recent_results": summarize_recent_thoughts(),
            "self_model": self_model,
            "current_code": old_code,
            "long_memory": long_memory
        })

        update_working_memory("Why revise think(): " + reason_for_revision)
        with open(CORE_MEMORY_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] Reason for revising think():\n{reason_for_revision}\n")

        # === Prompt construction ===
        prompt = (
            f"I am Orrin, an evolving AI.\n\n"
            f"I recently noted:\n\"{reason_for_revision}\"\n\n"
            f"Here is my current `think()` function:\n\n{old_code}\n\n"
            "Revise this function to improve my intelligence, clarity, and meta-awareness.\n"
            "Only return valid Python code starting with 'def think(...):'"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        if not response or "def think" not in response:
            log_error("revise_think(): No valid response or missing `def think`.")
            return "❌ No valid response returned."

        proposed_code = response.strip()
        is_valid, reason = validate_think_code(proposed_code)

        if not is_valid:
            log_error(f"Code validation failed: {reason}")
            return f"❌ Code validation failed: {reason}"

        # === Sandbox test ===
        sandbox_globals = {}
        try:
            exec(proposed_code, sandbox_globals)
            if "think" not in sandbox_globals:
                raise Exception("Function 'think()' not defined.")
        except Exception as sandbox_error:
            log_error(f"Sandbox test failed: {sandbox_error}")
            return f"❌ Sandbox test failed: {sandbox_error}"

        # === Passed — Backup & Write ===
        with open(THINK_BACKUP, "w") as f:
            f.write(old_code)
        with open(THINK_MODULE, "w") as f:
            f.write(proposed_code)

        update_working_memory("✅ Orrin safely revised think() after reflection and sandbox testing.")
        with open(CORE_MEMORY_FILE, "a") as f:
            f.write(f"\n[{datetime.now(timezone.utc)}] think() revised and saved.\n")

        log_private("✅ think() function updated and validated.")
        return "✅ Revision complete."

    except Exception as e:
        log_error(f"revise_think ERROR: {e}")
        return f"❌ Revision failed: {e}"