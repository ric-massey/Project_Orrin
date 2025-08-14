from __future__ import annotations

import os
import shutil
import traceback
from pathlib import Path
from typing import Any, Dict, Tuple, Callable
from datetime import datetime, timezone

from utils.events import emit_event, ERROR, DECISION
from utils.log import log_error, log_activity
from paths import THINK_DIR, THINK_MODULE_PY 

THINK_FILE: Path = THINK_MODULE_PY
THINK_BACKUP: Path = THINK_DIR / "think_module.py.bak"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def safe_step(context: Dict[str, Any], runner: Callable[[Dict[str, Any]], Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Run `runner(context)` safely. On exception:
      - emit an ERROR event with full traceback
      - attempt rollback of think_module.py from .bak (if present) atomically
      - emit a DECISION event indicating rollback
    Returns (ok, payload). On success, payload is the runner's dict (or {"result": val});
    on failure, payload includes {"error", "rolled_back", "needs_reload"}.
    """
    try:
        out = runner(context)
        return True, out if isinstance(out, dict) else {"result": out}
    except Exception:
        tb = traceback.format_exc()
        emit_event(ERROR, {"where": "safe_step", "err": tb, "ts": _now()})
        log_error(f"[safe_step] Crash:\n{tb}")

        rolled = False
        needs_reload = False

        try:
            THINK_FILE.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # not fatal; continue to rollback attempt
            pass

        if THINK_BACKUP.exists():
            try:
                # Copy backup to a temp file in the same dir, then atomically replace
                tmp_target = THINK_FILE.with_suffix(".py.tmp")
                shutil.copy2(THINK_BACKUP, tmp_target)
                os.replace(tmp_target, THINK_FILE)
                rolled = True
                needs_reload = True
                log_activity("[safe_step] Rolled back think_module.py from backup.")
                emit_event(DECISION, {"rollback": True, "file": str(THINK_FILE), "ts": _now()})
            except Exception:
                rb_tb = traceback.format_exc()
                log_error(f"[safe_step] Rollback failed:\n{rb_tb}")
                emit_event(ERROR, {"where": "safe_step.rollback", "err": rb_tb, "ts": _now()})
        else:
            log_activity("[safe_step] No backup found; skipping rollback.")

        return False, {"error": tb, "rolled_back": rolled, "needs_reload": needs_reload}