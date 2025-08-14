# skills_lib.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json, time, hashlib
from typing import Dict, Any, Optional
from paths import DATA_DIR
SKILLS_DIR: Path = DATA_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

def _skill_key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()

def _jsonable(obj: Any) -> Any:
    """Best-effort converter so we don't crash on non-serializable values."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return repr(obj)

def record_success(task_signature: str, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Path:
    """
    Append a success example to the skill's JSONL file.
    Returns the path to the JSONL.
    """
    k = _skill_key(task_signature)
    path = SKILLS_DIR / f"{k}.jsonl"
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "inputs": _jsonable(inputs),
        "outputs": _jsonable(outputs),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path

def maybe_distill(task_signature: str, min_successes: int = 2) -> Optional[Path]:
    """
    If we have >= min_successes for the signature, write a distilled skill stub.
    Returns the stub path if created/existing, else None.
    """
    k = _skill_key(task_signature)
    src = SKILLS_DIR / f"{k}.jsonl"
    if not src.exists():
        return None

    try:
        lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        return None

    if len(lines) < min_successes:
        return None

    stub = SKILLS_DIR / f"{k}_skill.py"
    if not stub.exists():
        stub.write_text(
            "# Auto-distilled skill (stub). Edit to generalize.\n"
            "from typing import Dict, Any\n\n"
            "def run(inputs: Dict[str, Any]) -> Dict[str, Any]:\n"
            "    # TODO: implement deterministic steps observed from past successes\n"
            "    # This stub just returns a success note for now.\n"
            "    return {'status': 'ok', 'note': 'stub'}\n",
            encoding='utf-8'
        )
    return stub