from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI
from dotenv import load_dotenv

from utils.json_utils import load_json
from utils.coerce_to_string import coerce_to_string
from cognition.selfhood.identity import build_system_prompt
from utils.log import log_model_issue
from core.config.settings import model_roles
from paths import MODEL_CONFIG_FILE, LLM_PROMPT
from utils.self_model import get_self_model

# --- Client singleton (lazy) ---
_client: Optional[OpenAI] = None

def _get_client() -> OpenAI:
    """Create the OpenAI client once; raise a friendly error if no key."""
    global _client
    if _client is None:
        load_dotenv()
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is missing. Set it in your .env.")
        _client = OpenAI(api_key=key)
    return _client

def get_thinking_model() -> str:
    # Fallback if callers use this module for the query-time model choice
    return model_roles.get("thinking", "gpt-4.1")

def _clamp(v: float, lo: float, hi: float) -> float:
    try:
        v = float(v)
    except Exception:
        return lo
    return max(lo, min(hi, v))

def _retry(fn, tries: int = 2, backoff: float = 0.5) -> Any:
    """
    Tiny exponential backoff retry for transient API failures (429/5xx/timeout).
    """
    last_err: Optional[Exception] = None
    for i in range(tries + 1):
        try:
            return fn()
        except Exception as e:
            msg = str(e).lower()
            transient = any(k in msg for k in ("timeout", "timed out", "rate limit", "429", "server error", "5"))
            if i == tries or not transient:
                last_err = e
                break
            time.sleep(backoff * (2 ** i))
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError("Retry loop exited without result.")

def generate_response(
    prompt: Any,
    model: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generate a chat completion with project-configured system prompt.

    Precedence for parameters:
      1) explicit `model` arg if provided
      2) keys from `config` dict (partial overrides allowed: model, temperature, max_tokens, system_prompt)
      3) selected block from MODEL_CONFIG_FILE (default→'thinking')
      4) hard defaults

    Returns: str | None
    """
    selected_cfg: Dict[str, Any] = {}
    try:
        # 1) Load repo MODEL_CONFIG (base)
        file_cfg = load_json(MODEL_CONFIG_FILE, default_type=dict) or {}
        default_key = (file_cfg or {}).get("default", "thinking")
        base_block = (file_cfg.get(default_key)
                      or file_cfg.get("thinking")
                      or {})

        # 2) Merge partial overrides from `config`
        if isinstance(config, dict):
            selected_cfg = {**base_block, **config}
        else:
            selected_cfg = dict(base_block)

        # 3) Apply explicit `model` parameter last
        if model is not None:
            selected_cfg["model"] = model

        # --- FLATTEN nested model blocks (defensive) ---
        mfield = selected_cfg.get("model")
        if isinstance(mfield, dict):
            nested = mfield
            # hoist common keys up if caller nested a full block under "model"
            for k in ("model", "temperature", "max_tokens", "system_prompt"):
                if k in nested and k not in selected_cfg:
                    selected_cfg[k] = nested[k]
            # ensure 'model' is a string going forward
            selected_cfg["model"] = nested.get("model") or nested.get("name") or "gpt-4.1"

        # 4) Coerce/derive final params
        sys_prompt_raw = selected_cfg.get("system_prompt", build_system_prompt(get_self_model()))
        system_prompt = coerce_to_string(sys_prompt_raw)

        raw_model = selected_cfg.get("model", "gpt-4.1")
        if isinstance(raw_model, dict):  # belt & suspenders
            raw_model = raw_model.get("model") or raw_model.get("name") or "gpt-4.1"
        model_name = coerce_to_string(raw_model).strip()
        if not model_name or "{" in model_name or "}" in model_name:
            raise TypeError(f"model must be a non-empty model id string, got: {raw_model!r}")

        temperature = _clamp(selected_cfg.get("temperature", 0.85), 0.0, 2.0)
        max_tokens = int(_clamp(selected_cfg.get("max_tokens", 2048), 1, 8192))

        user_prompt = coerce_to_string(prompt)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for i, msg in enumerate(messages):
            if not isinstance(msg["content"], str):
                raise TypeError(f"messages[{i}]['content'] must be str, got {type(msg['content'])!r}")

        # Ensure prompt log directory exists
        lp = Path(LLM_PROMPT)
        lp.parent.mkdir(parents=True, exist_ok=True)

        # Log request
        with lp.open("a", encoding="utf-8") as f:
            f.write(f"\n\n=== {datetime.now(timezone.utc).isoformat()} ===\n")
            f.write("SYSTEM PROMPT:\n" + system_prompt + "\n\n")
            f.write("USER PROMPT:\n" + user_prompt + "\n\n")

        client = _get_client()

        def _call():
            return client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        resp = _retry(_call, tries=2, backoff=0.5)
        reply = (resp.choices[0].message.content or "").strip()

        # Log response
        with lp.open("a", encoding="utf-8") as f:
            f.write("LLM RESPONSE:\n" + reply + "\n")

        return reply or None

    except Exception as e:
        # Keep context, but guard against repr explosions
        try:
            cfg_repr = repr(selected_cfg)
        except Exception:
            cfg_repr = "{}"
        log_model_issue(f"[generate_response] API failure: {e} | config: {cfg_repr}")
        return None
