# minimal_eval_runner.py
# Minimal eval runner that logs EVAL events and pass/fail.

import os
import json
from typing import Dict, Any
from pathlib import Path

# --- paths & dirs ---
try:
    from paths import ROOT_DIR
except Exception:
    ROOT_DIR = Path(__file__).resolve().parent
EVALS_DIR: Path = (ROOT_DIR / "evals" / "task_suites")
EVALS_DIR.mkdir(parents=True, exist_ok=True)

# --- eval predicate ---
try:
    from cognition.planning.goals_schema import eval_predicate
except Exception as e:
    raise ImportError(f"Cannot import eval_predicate: {e}")

# --- logging (avoid stdlib 'logging' package name) ---
try:
    from loggit.event_logger import log_event, EventKind
except Exception:
    class _EventKind:
        EVAL = "EVAL"
        ERROR = "ERROR"
    EventKind = _EventKind()

    def log_event(kind, **kwargs):
        kind_str = getattr(kind, "value", None) or (kind if isinstance(kind, str) else str(kind))
        print(json.dumps({"kind": kind_str, **kwargs}, ensure_ascii=False))

def run_suite(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            suite = json.load(f)
    except Exception as e:
        log_event(EventKind.ERROR, msg="Failed to load suite", path=str(path), error=str(e))
        return {"suite": path.stem, "passed": 0, "total": 0, "error": str(e)}

    suite_name = suite.get("name", path.stem)
    tasks = suite.get("tasks", [])
    if not isinstance(tasks, list):
        log_event(EventKind.ERROR, msg="Suite 'tasks' is not a list", suite=suite_name, path=str(path))
        return {"suite": suite_name, "passed": 0, "total": 0, "error": "invalid_tasks"}

    passed = 0
    total = 0

    for t in tasks:
        if not isinstance(t, dict):
            continue
        task_id = t.get("id", f"task_{total}")
        check = t.get("check")
        if check is None:
            log_event(EventKind.ERROR, msg="Task missing 'check'", suite=suite_name, task=task_id)
            continue

        # TODO: integrate your pipeline stdout capture here
        simulated_stdout = ""  # replace with real captured output
        ctx = {"stdout": simulated_stdout}

        try:
            ok = bool(eval_predicate(check, ctx))
        except Exception as e:
            ok = False
            log_event(EventKind.ERROR, msg="eval_predicate failed", suite=suite_name, task=task_id, error=str(e))

        log_event(EventKind.EVAL, suite=suite_name, task=task_id, passed=ok)
        passed += 1 if ok else 0
        total += 1

    return {"suite": suite_name, "passed": passed, "total": total}

if __name__ == "__main__":
    results = []
    for fn in sorted(EVALS_DIR.iterdir()):
        if fn.is_file() and fn.suffix.lower() == ".json":
            res = run_suite(fn)
            print(res)
            results.append(res)
    if results:
        agg_passed = sum(r.get("passed", 0) for r in results)
        agg_total = sum(r.get("total", 0) for r in results)
        print({"all_suites_passed": agg_passed, "all_suites_total": agg_total})