from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import json

from cognition.reflection.meta_reflect import meta_reflect
from utils.code_validation import validate_think_code
from memory.working_memory import update_working_memory
from utils.json_utils import load_json
from utils.append import append_to_json
from utils.log import log_error, log_private
from utils.generate_response import generate_response, get_thinking_model
from utils.summarizers import summarize_recent_thoughts
from utils.self_model import get_self_model
from think.sandbox_runner import run_python  # <-- NEW

from paths import (
    LONG_MEMORY_FILE,
    CORE_MEMORY_FILE,
    THINK_MODULE_PY,
    THINK_DIR,
    ROOT_DIR,                # <-- NEW (cwd for sandbox so package imports resolve)
    ensure_files,
)

# Canonical paths
THINK_MODULE: Path = THINK_MODULE_PY
THINK_BACKUP: Path = THINK_DIR / "think_module_backup.py"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_code(raw: str) -> str:
    """
    Normalize LLM output:
    - remove ```python ... ``` fences if present
    - trim leading text before 'def think'
    """
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    idx = s.find("def think")
    if idx > 0:
        s = s[idx:]
    return s


def _sandbox_check_defines_think(code: str) -> tuple[bool, str]:
    """
    Run the candidate code in an isolated Python process and verify it defines a callable think().
    We print a small JSON object from inside the sandbox so we can parse stdout reliably.
    """
    wrapper = f"""# auto-generated sandbox wrapper
import json, inspect
# ---- begin candidate code ----
{code}
# ---- end candidate code ----
defined = bool('think' in globals() and callable(think))
sig = None
if defined:
    try:
        sig = str(inspect.signature(think))
    except Exception as e:
        sig = f"<sig-error: {{e}}>"
print(json.dumps({{"defined": defined, "signature": sig}}))
"""
    res = run_python(wrapper, timeout=5.0, cwd=str(ROOT_DIR))
    if not res.get("ok", False):
        # Could be syntax error or import error at module import time
        return False, f"sandbox error (rc={res.get('returncode')}): {res.get('stderr') or 'unknown'}"

    # Parse the LAST json-looking line from stdout (be forgiving of user prints)
    defined = False
    signature = ""
    for line in (res.get("stdout") or "").splitlines()[::-1]:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                defined = bool(obj.get("defined", False))
                signature = str(obj.get("signature", ""))
                break
            except Exception:
                continue

    if not defined:
        return False, f"sandbox: think() not defined or not callable. stdout={res.get('stdout')!r} stderr={res.get('stderr')!r}"
    return True, signature or ""


def revise_think() -> str:
    """
    Reflectively rewrite think() using recent thoughts, internal state, and past results.
    Writes a validated revision into THINK_MODULE with a backup, after sandbox verification.
    """
    try:
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        self_model = get_self_model()

        # Ensure module/backup files exist
        ensure_files([THINK_MODULE, THINK_BACKUP])

        # --- Load current think() code ---
        try:
            old_code = THINK_MODULE.read_text(encoding="utf-8")
        except FileNotFoundError:
            log_error(f"{THINK_MODULE.name} not found.")
            return "❌ think_module.py not found."

        # --- Reflect on why revision is needed ---
        reason_for_revision = meta_reflect({
            "goal": "Improve my own thinking process",
            "recent_results": summarize_recent_thoughts(),
            "self_model": self_model,
            "current_code": old_code,
            "long_memory": long_memory,
        })

        update_working_memory("Why revise think(): " + str(reason_for_revision))
        append_to_json(CORE_MEMORY_FILE, {
            "event": "reason_for_revision_think",
            "reason": reason_for_revision,
            "timestamp": _utc_now(),
        })

        # --- Prompt the model for new code ---
        prompt = (
            "I am Orrin, an evolving AI.\n\n"
            f"I recently noted:\n\"{reason_for_revision}\"\n\n"
            "Here is my current `think()` function:\n\n"
            f"{old_code}\n\n"
            "Revise this function to improve my intelligence, clarity, and meta-awareness.\n"
            "Only return valid Python code starting with 'def think':"
        )

        response = generate_response(prompt, config={"model": get_thinking_model()})
        code = _extract_code(response)

        if not code or not code.lstrip().startswith("def think"):
            log_error("revise_think(): No valid response or missing `def think`.")
            return "❌ No valid response returned."

        # --- Validate code shape/content ---
        is_valid, reason = validate_think_code(code)
        if not is_valid:
            log_error(f"Code validation failed: {reason}")
            return f"❌ Code validation failed: {reason}"

        # --- Sandbox verification (OUT-OF-PROCESS) ---
        ok, detail = _sandbox_check_defines_think(code)
        if not ok:
            log_error(f"Sandbox verification failed: {detail}")
            return f"❌ Sandbox verification failed: {detail}"

        # --- Passed — Backup & Write ---
        THINK_BACKUP.write_text(old_code, encoding="utf-8")
        THINK_MODULE.write_text(code, encoding="utf-8")

        update_working_memory("✅ Orrin safely revised think() after reflection and sandbox execution test.")
        append_to_json(CORE_MEMORY_FILE, {"event": "think_revised", "timestamp": _utc_now()})
        log_private(f"✅ think() updated. signature={detail or '<unknown>'}")
        return "✅ Revision complete."

    except Exception as e:
        log_error(f"revise_think ERROR: {e}")
        return f"❌ Revision failed: {e}"
