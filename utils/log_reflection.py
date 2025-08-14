from __future__ import annotations
from pathlib import Path
from typing import Any, Union
from datetime import datetime, timezone

from utils.append import append_to_json
from utils.log import log_model_issue
from paths import REFLECTION  # Path to data/reflection_log.json


def _ensure_pathlike(p: Union[str, Path], label: str = "file_path") -> Path:
    """
    Reject list/tuple (the source of the 'not list' TypeError) and coerce to Path.
    """
    if isinstance(p, (list, tuple)):
        raise TypeError(f"{label} must be a single path, not a list/tuple: {p!r}")
    return Path(p)


def log_reflection(
    message: Any,
    reflection_type: str = "unspecified",
    file_path: Union[str, Path] = REFLECTION,
) -> None:
    """
    Append a reflection entry to the reflection log (JSON array).
    Keeps cognition resilient: on failure we record a model issue instead of raising.
    """
    try:
        p = _ensure_pathlike(file_path, "log_reflection.file_path")
        entry = {
            "type": str(reflection_type),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": ("" if message is None else str(message)).strip(),
        }
        append_to_json(p, entry)   # must accept Path/str
    except Exception as e:
        # Don’t crash cognition if the log write fails; capture for repair/triage.
        log_model_issue(f"[log_reflection] failed: {e}")
