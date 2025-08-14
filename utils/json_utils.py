import re
import json
import tempfile
import os
import platform
from pathlib import Path, PurePath
from datetime import datetime, date
from typing import Any, Callable, TypeVar, Union, Optional
from utils.log import log_model_issue

# fcntl is POSIX-only; make it optional
try:
    import fcntl  # type: ignore
except Exception:
    fcntl = None  # type: ignore

T = TypeVar("T")

# ------------------------------
# JSON extraction (healing)
# ------------------------------

def extract_json(text: str) -> Optional[Union[dict, list]]:
    """
    Best-effort extraction of the first JSON object/array from messy LLM output.
    Order:
      1) ```json fenced block
      2) generic ``` fenced block
      3) first JSON fragment via scanner (try parse → heal → salvage-top-level-object)
      4) whole text heal → salvage-top-level-object
    Returns dict/list, else None.
    """
    try:
        s = text if isinstance(text, str) else str(text)

        # 1) fenced with json
        m = re.search(r"```(?:json|JSON)\s*([\s\S]*?)\s*```", s)
        if m:
            snippet = m.group(1).strip()
            # try straight
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass
            # heal then try
            healed = _heal_json_fragment(snippet)
            try:
                return json.loads(healed)
            except Exception:
                # salvage as last-ditch
                salv = _salvage_top_level_object(snippet)
                if salv:
                    try:
                        return json.loads(salv)
                    except Exception:
                        pass

        # 2) any fenced block
        m = re.search(r"```+\s*([\s\S]*?)\s*```+", s)
        if m:
            snippet = m.group(1).strip()
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                healed = _heal_json_fragment(snippet)
                try:
                    return json.loads(healed)
                except Exception:
                    salv = _salvage_top_level_object(snippet)
                    if salv:
                        try:
                            return json.loads(salv)
                        except Exception:
                            pass

        # 3) scan for top-level {...} or [...]
        frag = _first_json_fragment(s)
        if frag:
            # direct
            try:
                return json.loads(frag)
            except json.JSONDecodeError:
                pass
            # heal
            healed = _heal_json_fragment(frag)
            try:
                return json.loads(healed)
            except Exception:
                pass
            # salvage top-level object specifically (handles cut off like "..., \"emerging_conflicts\": [")
            salv = _salvage_top_level_object(frag)
            if salv:
                try:
                    return json.loads(salv)
                except Exception:
                    pass

        # 4) whole text attempts
        healed_all = _heal_json_fragment(s)
        try:
            return json.loads(healed_all)
        except Exception:
            pass

        salv_all = _salvage_top_level_object(s)
        if salv_all:
            try:
                return json.loads(salv_all)
            except Exception:
                pass

    except Exception as e:
        preview = s if len(s) <= 600 else (s[:300] + " ... " + s[-200:])
        log_model_issue(f"[extract_json] Failed: {e}\nRaw: {preview}")

    return None


def _first_json_fragment(s: str) -> Optional[str]:
    """Return the first candidate JSON {...} or [...] substring (may be unbalanced if truncated)."""
    i_obj, i_arr = s.find("{"), s.find("[")
    starts = [i for i in (i_obj, i_arr) if i != -1]
    if not starts:
        return None
    start = min(starts)

    open_ch = s[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch and depth > 0:
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    # unbalanced (truncated) → return tail so we can heal it
    return s[start:]


def _heal_json_fragment(frag: str) -> str:
    """
    Light repairs for slightly invalid/truncated JSON:
    - remove trailing commas before } or ]
    - close open string
    - balance unmatched braces/brackets
    """
    t = frag.rstrip()
    t = t.replace(",}", "}").replace(",]", "]")

    in_str = False
    esc = False
    depth_obj = 0
    depth_arr = 0
    for ch in t:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth_obj += 1
            elif ch == "}":
                depth_obj = max(0, depth_obj - 1)
            elif ch == "[":
                depth_arr += 1
            elif ch == "]":
                depth_arr = max(0, depth_arr - 1)

    if in_str:
        t += '"'
    t += "}" * depth_obj
    t += "]" * depth_arr
    t = t.replace(",}", "}").replace(",]", "]")
    return t


def _salvage_top_level_object(text: str) -> Optional[str]:
    """
    Try to salvage a valid top-level JSON *object* from truncated text:
    - Find first '{'
    - Walk tracking quotes/escapes and nesting
    - If we close level 0, return slice
    - If truncated inside the object, cut at the last comma at level==1 and append '}'.
      If that fails, append enough '}' to close remaining depth.
    """
    s = text
    start = s.find("{")
    if start == -1:
        return None

    level = 0
    in_str = False
    esc = False
    last_top_level_comma: Optional[int] = None

    i = start
    while i < len(s):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                level += 1
            elif ch == "}":
                if level > 0:
                    level -= 1
                    if level == 0:
                        return s[start:i+1]
            elif ch == "," and level == 1:
                last_top_level_comma = i
        i += 1

    # Truncated before closing: try cutting at last full top-level pair
    if last_top_level_comma is not None:
        candidate = s[start:last_top_level_comma] + "}"
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    # Blindly close remaining braces
    if level > 0:
        candidate = s[start:] + ("}" * level)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    return None


# ------------------------------
# JSON (de)serialization utils
# ------------------------------

def _json_default(o: Any):
    """Safe fallback serializer for non-JSON-native types."""
    if isinstance(o, (Path, PurePath)):
        return str(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, set):
        return list(o)
    if isinstance(o, bytes):
        return o.decode("utf-8", "ignore")
    # tuples, enums, custom objects, etc.
    return str(o)


def save_json(filepath: Union[str, Path], data: Any) -> None:
    """
    Atomically write JSON to disk.
    - Write to a temp file in the same dir, fsync, then os.replace(...) atomically.
    - Serialize writers via a well-known .lock file on POSIX (advisory).
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    lock_fd = None
    tmp_name: Optional[str] = None
    lock_path = path.with_suffix(path.suffix + ".lock")

    try:
        # Acquire inter-process advisory lock (POSIX only)
        if fcntl is not None:
            lock_fd = open(lock_path, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # Write to temp in the same dir to guarantee atomic rename
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=str(path.parent), encoding="utf-8"
        ) as tmp:
            tmp_name = tmp.name
            json.dump(data, tmp, indent=2, ensure_ascii=False, default=_json_default)
            tmp.flush()
            os.fsync(tmp.fileno())

        # Atomic replace (POSIX/Windows)
        os.replace(tmp_name, path)

    except Exception as e:
        # Clean up stray temp if we created one
        try:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass
        log_model_issue(f"[save_json] Failed to save {filepath}: {e}")
    finally:
        if fcntl is not None and lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                try:
                    lock_fd.close()
                finally:
                    # lockfile is just a coordination token; safe to remove
                    try:
                        os.unlink(lock_path)
                    except Exception:
                        pass


def load_json(filepath: Union[str, Path], default_type: Callable[[], T] = dict) -> T:
    """
    Load JSON from file, returning default_type() on error or missing/empty file.
    """
    try:
        path = Path(filepath)
        if not path.exists() or path.stat().st_size == 0:
            return default_type()
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_model_issue(f"[load_json] Failed to load {filepath}: {e}")
        return default_type()


def append_jsonl(filepath: Union[str, Path], obj: Any) -> None:
    """
    Append one JSON-serialized line to a .jsonl file.
    - Ensures parent directory exists.
    - Uses advisory flock on Unix to avoid interleaved writes.
    - fsyncs to reduce data loss on crash.
    """
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False, default=_json_default) + "\n"

        # Open in append mode; create if missing
        with open(path, "a", encoding="utf-8") as f:
            if fcntl is not None and platform.system() != "Windows":
                try:
                    fcntl.flock(f, fcntl.LOCK_EX)  # type: ignore[name-defined]
                except Exception:
                    pass  # don't fail logging if flock not available
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
            if fcntl is not None and platform.system() != "Windows":
                try:
                    fcntl.flock(f, fcntl.LOCK_UN)  # type: ignore[name-defined]
                except Exception:
                    pass
    except Exception as e:
        log_model_issue(f"[append_jsonl] Failed to append to {filepath}: {e}")
