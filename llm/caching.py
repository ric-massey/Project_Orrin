from __future__ import annotations
import json, os, hashlib, time
from typing import Any, Callable, Dict, Optional
from pathlib import Path

# Project paths (you said you always run from root, so this can be direct)
from paths import cache_file  # returns a Path to DATA_DIR/<key>.json

def _normalize(val: Any) -> Any:
    """Make values JSON-stable for hashing: sort dicts, normalize sequences, round floats."""
    if isinstance(val, dict):
        return {k: _normalize(val[k]) for k in sorted(val)}
    if isinstance(val, (list, tuple)):
        return [_normalize(v) for v in val]  # tuples -> lists for JSON
    if isinstance(val, float):
        return round(val, 3)  # avoid tiny drift changing keys
    return val

def _cache_key(*, namespace: str = "", **kv: Any) -> str:
    payload = {"__ns__": namespace, **{k: _normalize(v) for k, v in sorted(kv.items())}}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

def _read_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupted / partial cache — ignore it
        return None

def _atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic on POSIX and Windows

def cached_generate_response(
    fn: Callable[..., Dict[str, Any]],
    *,
    prompt: str,
    model: str,
    system: str = "",
    temperature: float = 0.7,
    tools_signature: str = "",
    max_tokens: int = 2048,
    namespace: str = "llm-cache",
    ttl_seconds: Optional[int] = None,
    force_refresh: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    File-backed response cache.

    Hashes (prompt, model, system, temperature, tools_signature, max_tokens, kwargs)
    to a stable key and stores JSON response at paths.cache_file(key).

    Options:
      - namespace: logical bucket to keep caches isolated
      - ttl_seconds: expire cache after N seconds (None = never)
      - force_refresh: bypass cache and re-compute
    """
    key = _cache_key(
        namespace=namespace,
        prompt=prompt,
        model=model,
        system=system,
        temperature=temperature,
        tools_signature=tools_signature,
        max_tokens=max_tokens,
        kwargs=_normalize(kwargs),
    )
    path = cache_file(key)  # Path object

    if not force_refresh and path.exists():
        # TTL check (if set)
        if ttl_seconds is None or (time.time() - path.stat().st_mtime) <= ttl_seconds:
            cached = _read_json_safe(path)
            if cached is not None:
                return cached

    # Compute fresh
    resp = fn(
        prompt=prompt,
        model=model,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )

    # Ensure JSON-serializable
    try:
        _atomic_write_json(path, resp)  # may raise if not serializable
    except TypeError:
        # Best effort: coerce to stringy JSON
        safe_resp = json.loads(json.dumps(resp, default=str))
        _atomic_write_json(path, safe_resp)
        return safe_resp

    return resp