# competence.py
from __future__ import annotations
from pathlib import Path
import json, time
from statistics import median
from typing import Dict, Any

# --- standardized import for project paths (explicit, robust) ---
DATA_DIR: Path
COMPETENCE_DB: Path
ensure_files = None  # type: ignore

def _try_import_paths() -> bool:
    global DATA_DIR, COMPETENCE_DB, ensure_files
    try:
        # Prefer canonical constants from paths.py
        from paths import DATA_DIR as _DATA_DIR, COMPETENCE_JSON as _COMPETENCE_DB, ensure_files as _ensure_files
        DATA_DIR = _DATA_DIR
        COMPETENCE_DB = _COMPETENCE_DB  # use the shared constant
        ensure_files = _ensure_files
        return True
    except Exception:
        # Fallback: try without COMPETENCE_JSON (older paths.py)
        try:
            from paths import DATA_DIR as _DATA_DIR, ensure_files as _ensure_files
            DATA_DIR = _DATA_DIR
            ensure_files = _ensure_files
            COMPETENCE_DB = DATA_DIR / "competence.json"
            return True
        except Exception:
            return False

def _search_and_import_paths() -> bool:
    """Search up to 8 levels for paths.py, then import it."""
    import sys
    base = Path(__file__).resolve().parent
    for _ in range(8):
        candidate = base / "paths.py"
        if candidate.exists():
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            return _try_import_paths()
        base = base.parent
    return False

if not _try_import_paths():
    _search_and_import_paths()

# Final fallback if paths.py is not found anywhere
if "DATA_DIR" not in globals():
    DATA_DIR = Path(__file__).resolve().parent / "data"
    COMPETENCE_DB = DATA_DIR / "competence.json"

    def ensure_files(paths: list[Path]) -> None:  # minimal local fallback
        for p in paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.touch()
# --- end standardized import ---

def _load() -> Dict[str, Any]:
    if not COMPETENCE_DB.exists():
        return {}
    try:
        return json.loads(COMPETENCE_DB.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        # Corrupt/partial write: recover gracefully
        return {}

def _save(db: Dict[str, Any]) -> None:
    ensure_files([COMPETENCE_DB])
    COMPETENCE_DB.write_text(json.dumps(db, indent=2), encoding="utf-8")

def record(skill: str, success: bool, attempts: int) -> None:
    db = _load()
    rec = db.get(skill, {"history": []})
    rec["history"].append({
        "ts": time.time(),
        "success": bool(success),
        "attempts": int(attempts),
    })
    hist = rec["history"][-100:]
    succ = sum(1 for h in hist if h["success"])
    rec["success_rate"] = succ / len(hist) if hist else 0.0
    rec["median_attempts"] = median([h["attempts"] for h in hist]) if hist else 0
    rec["last_used"] = time.time()
    db[skill] = rec
    _save(db)