import os
import re
import time
import random
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

from emotion.emotion import detect_emotion
from utils.json_utils import load_json, save_json, extract_json
from core.config.settings import model_roles
from utils.log import log_model_issue, log_activity
from utils.generate_response import generate_response, get_thinking_model
from paths import KNOWLEDGE

load_dotenv()

def get_human_model():
    return model_roles.get("human_facing", "gpt-4.1")

def _normalize_text(s: str) -> str:
    """Trim and collapse internal whitespace for reliable de-dup checks."""
    return re.sub(r"\s+", " ", (s or "").strip())

def extract_knowledge_from_reflection(reflection_text: str) -> None:
    """
    Ask the LLM to extract reusable knowledge snippets from a reflection and
    append them to KNOWLEDGE, avoiding duplicates.
    """
    prompt = (
        "Extract reusable insights or principles from the following:\n\n"
        f"{reflection_text}\n\n"
        "Respond ONLY with a JSON list of short knowledge snippets."
    )
    try:
        response = generate_response(prompt)
        snippets = extract_json(response)
        if not isinstance(snippets, list):
            raise ValueError("LLM did not return a JSON list.")

        existing = load_json(KNOWLEDGE, default_type=list)
        if not isinstance(existing, list):
            existing = []

        existing_summaries = { _normalize_text(e.get("summary", "")) for e in existing if isinstance(e, dict) }

        added = 0
        for snippet in snippets:
            text = snippet if isinstance(snippet, str) else (snippet or {}).get("summary", "")
            norm = _normalize_text(text)
            if not norm or norm in existing_summaries:
                continue

            # simple keyword fallback
            keywords = sorted({w for w in norm.lower().split() if len(w) > 3 and w.isalpha()})

            entry = {
                "id": str(uuid.uuid4()),
                "summary": norm,
                "source": reflection_text[:80],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "reflection",
                "emotion": detect_emotion(norm),   # ok if this returns str or dict in your schema
                "confidence": 0.8,
                "relevance": keywords,
                "reference_count": 0,
            }
            existing.append(entry)
            existing_summaries.add(norm)
            added += 1

        if added:
            save_json(KNOWLEDGE, existing)
            log_activity(f"[knowledge] Added {added} snippet(s) from reflection.")
    except Exception as e:
        log_model_issue(f"[extract_knowledge_from_reflection] Failed: {e}")

# Multiline, tolerant question extraction (captures sentences ending with '?')
_QUESTION_RE = re.compile(r"(^|[.!\n]\s*)([^?.!\n][^?]*\?)", re.MULTILINE)

def extract_questions(text: str):
    # Return distinct, reasonably long questions
    candidates = [m[1].strip() for m in _QUESTION_RE.findall(text or "")]
    uniq = []
    for q in candidates:
        if len(q) > 10 and q not in uniq:
            uniq.append(q)
    return uniq

def rate_satisfaction(thought: str) -> float:
    """
    Ask the LLM to rate satisfaction 0..1. Returns 0.0 on parse error.
    """
    prompt = (
        f"Reflect on this thought:\n{thought}\n\n"
        "On a scale from 0 to 1, how satisfying or complete is this answer?\n"
        "Respond ONLY with a single float (like 0.0, 0.7, or 1.0) and NO other words or explanation."
    )
    try:
        model_name = get_thinking_model()
        if isinstance(model_name, dict):
            model_name = model_name.get("model", "gpt-4.1")
        resp = generate_response(prompt, model=model_name)
        log_activity(f"[rate_satisfaction] Raw LLM response: {repr(resp)}")

        m = re.search(r"(?<!\d)(?:0(?:\.\d+)?|1(?:\.0+)?)|(?:\.\d+)", str(resp))
        if m:
            val = float(m.group())
            # if we matched ".8", Python parses OK; clamp safety
            return max(0.0, min(1.0, val))
        # extreme minimal fallbacks
        s = str(resp).strip()
        if s == "1": return 1.0
        if s == "0": return 0.0
    except Exception as e:
        log_model_issue(f"[rate_satisfaction] parse error: {e}")
    return 0.0

def delay_between_requests(min_sec: float = 2, max_sec: float = 5) -> None:
    time.sleep(random.uniform(min_sec, max_sec))

def extract_lessons(memories):
    """
    Pull 'lesson' strings out of a list of memory dicts, via explicit key
    or common textual prefix. Returns a list of normalized lessons.
    """
    out = []
    for m in (memories or []):
        try:
            if isinstance(m, dict) and "lesson" in m:
                lesson_text = _normalize_text(str(m["lesson"]))
                if lesson_text:
                    out.append(lesson_text)
                continue

            content = _normalize_text(m.get("content", "")) if isinstance(m, dict) else ""
            lower = content.lower()
            if lower.startswith("lesson learned:"):
                text = _normalize_text(content[len("lesson learned:"):])
                if text:
                    out.append(text)
            elif lower.startswith("lesson:"):
                text = _normalize_text(content[len("lesson:"):])
                if text:
                    out.append(text)
        except Exception:
            continue
    # Optional de-dup
    seen = set()
    deduped = []
    for l in out:
        if l not in seen:
            seen.add(l)
            deduped.append(l)
    return deduped