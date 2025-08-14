from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union

def ruff_fix(
    path: Union[str, Path],
    *,
    timeout: Optional[float] = 120,
    cwd: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """
    Run `ruff check --fix` on the given file or directory.

    Returns:
        - Combined stdout+stderr from Ruff (even on non-zero exit), or
        - None if Ruff is not installed.

    Raises:
        - FileNotFoundError if the target path does not exist (and Ruff is present).
        - subprocess.TimeoutExpired if the process exceeds `timeout`.
    """
    if shutil.which("ruff") is None:
        return None  # Ruff not installed / not on PATH

    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")

    proc = subprocess.run(
        ["ruff", "check", str(target), "--fix"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd is not None else None,
    )
    # Always return output; caller can inspect `proc.returncode` if needed by parsing.
    return (proc.stdout or "") + (proc.stderr or "")