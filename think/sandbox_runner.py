# think/sandbox_runner.py
from __future__ import annotations
import subprocess, sys, tempfile, json, os
from typing import Dict, Any

def run_python(code: str, timeout: float = 5.0, cwd: str | None = None) -> Dict[str, Any]:
    """
    Execute untrusted Python in a *separate* process with -I (isolated) & -S (no site),
    returning {"ok": bool, "stdout": str, "stderr": str, "returncode": int}.
    """
    if not isinstance(code, str):
        return {"ok": False, "stdout": "", "stderr": "code must be str", "returncode": -1}

    py = sys.executable
    env = {"PYTHONIOENCODING": "utf-8"}  # no secrets
    # Optionally whitelist cwd to a temp dir
    work = cwd or tempfile.mkdtemp(prefix="orrin_sbx_")

    # Write code to a temp file to avoid shell quoting issues
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=work, delete=False) as f:
        f.write(code)
        path = f.name

    try:
        proc = subprocess.run(
            [py, "-I", "-S", path],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "returncode": -9}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "returncode": -2}
