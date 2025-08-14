# utils/emotional_response.py
from __future__ import annotations

from typing import Any, Dict, Optional
from emotion.amygdala import process_emotional_signals
from utils.generate_response import generate_response

def generate_emotional_response(
    prompt: str,
    model: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Run prompt through the amygdala first; if a threat shortcut is triggered,
    return a short-circuit message; otherwise delegate to the LLM.

    Returns a string response (or an error-style string if the shortcut fired).
    """
    context: Dict[str, Any] = {
        "input_text": prompt,
        "mode": {"mode": "thinking"},
    }

    try:
        context, amygdala_response = process_emotional_signals(context)
    except Exception:
        # If the amygdala path fails for any reason, fall back to normal generation
        return generate_response(prompt, model=model, config=config)

    threat = bool(amygdala_response and amygdala_response.get("threat_detected"))
    if threat:
        shortcut = amygdala_response.get("shortcut_function") or "safety_reflex"
        tags = amygdala_response.get("threat_tags", [])
        return f"⚠️ Amygdala triggered a shortcut: {shortcut} due to {tags}"

    # No threat—proceed normally
    return generate_response(prompt, model=model, config=config)