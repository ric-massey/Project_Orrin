from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union, Dict, Any

from paths import ERROR_FILE, MODEL_FAILURE, ACTIVITY_LOG, PRIVATE_THOUGHTS_FILE

# --- helpers ---
def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()

def _append_line(p: Path, line: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)

# --- writers ---
def log_error(content: Any) -> None:
    _append_line(ERROR_FILE, f"\n[{_ts()}] {str(content)}\n")

def log_model_issue(message: Any) -> None:
    _append_line(MODEL_FAILURE, f"[{_ts()}] {str(message)}\n")

def log_activity(message: Any) -> None:
    _append_line(ACTIVITY_LOG, f"[{_ts()}] {str(message)}\n")

def log_private(message: Any) -> None:
    _append_line(PRIVATE_THOUGHTS_FILE, f"[{_ts()}] {str(message)}\n")

# --- readers ---
def read_recent_errors_txt(path: Union[str, Path], max_lines: int = 5) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-max_lines:] if lines else []
    except Exception as e:
        return [f"⚠️ Failed to read {path}: {e}"]

def read_recent_errors_json(path: Union[str, Path], max_items: int = 5) -> List[Dict[str, Any]]:
    from utils.json_utils import load_json
    try:
        data = load_json(path, default_type=list)
        return data[-max_items:] if isinstance(data, list) else []
    except Exception as e:
        return [{"error": f"⚠️ Failed to read {path}: {e}"}]