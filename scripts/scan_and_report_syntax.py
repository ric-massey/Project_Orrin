# scan_repo.py
# Scan repo for syntax errors and suspicious ellipses in source & docs.

import os
import re
import sys
import ast
from pathlib import Path
from typing import List, Tuple

SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules", ".mypy_cache", ".pytest_cache"}
PY_EXT = {".py"}
TEXT_EXT = {".md", ".txt"}
ELLIPSIS_UTF8 = "…"
ELLIPSIS_RE = re.compile(r"\.\.\.(\s*$)")  # literal '...' at end of line (possible truncation)

Issue = Tuple[str, str, str]  # (path, kind, message)

def _should_skip_dir(d: str) -> bool:
    base = os.path.basename(d)
    return base in SKIP_DIRS or base.startswith(".")

def _scan_text_for_ellipsis(src: str) -> List[str]:
    msgs = []
    if ELLIPSIS_UTF8 in src:
        msgs.append("contains Unicode ellipsis (…): possible truncation or placeholder")
    # line-ending '...'
    for i, line in enumerate(src.splitlines(), start=1):
        if ELLIPSIS_RE.search(line):
            msgs.append(f"line {i}: ends with '...' (possible truncation)")
    return msgs

def scan(root: str = ".") -> List[Issue]:
    issues: List[Issue] = []
    root_path = Path(root)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # prune dirs in-place
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(os.path.join(dirpath, d))]

        for fn in filenames:
            p = Path(dirpath) / fn
            ext = p.suffix.lower()

            # Only consider Python and text files
            if ext not in PY_EXT | TEXT_EXT:
                continue

            # Read file (be forgiving about encoding)
            try:
                src = p.read_text(encoding="utf-8")
            except UnicodeDecodeError as e:
                issues.append((str(p), "READ_DECODE", f"Could not decode as UTF-8: {e}"))
                try:
                    # Try with replacement to keep scanning
                    src = p.read_text(encoding="utf-8", errors="replace")
                except Exception as e2:
                    issues.append((str(p), "READ", f"Failed to read with replacement: {e2}"))
                    continue
            except Exception as e:
                issues.append((str(p), "READ", str(e)))
                continue

            # Text ellipsis checks for both .py and docs
            for msg in _scan_text_for_ellipsis(src):
                issues.append((str(p), "ELLIPSIS", msg))

            # Syntax check only for Python files
            if ext in PY_EXT:
                try:
                    ast.parse(src, filename=str(p))
                except SyntaxError as e:
                    issues.append((str(p), "SYNTAX", f"{e.msg} at line {e.lineno} col {e.offset}"))
                except Exception as e:
                    issues.append((str(p), "PARSE", str(e)))

    return issues

def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    issues = scan(root)
    for path, kind, msg in issues:
        print(f"{kind}\t{path}\t{msg}")
    print(f"TOTAL_ISSUES\t{len(issues)}")

    # optional summary by kind
    if issues:
        counts = {}
        for _, k, _ in issues:
            counts[k] = counts.get(k, 0) + 1
        print("SUMMARY_BY_KIND\t" + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
    return 0 if not any(k in {"SYNTAX", "PARSE"} for _, k, _ in issues) else 1

if __name__ == "__main__":
    raise SystemExit(main())