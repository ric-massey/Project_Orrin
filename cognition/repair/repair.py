# === Imports ===
from __future__ import annotations

import json
from datetime import datetime, timezone

from utils.json_utils import load_json, save_json, extract_json
from utils.log import log_error, log_private, log_model_issue, log_activity
from utils.log_reflection import log_reflection
from utils.generate_response import generate_response, get_thinking_model
from utils.load_utils import load_all_known_json
from utils.feedback_log import log_feedback
from utils.response_utils import generate_response_from_context
from cognition.reflection.reflect_on_cognition import update_cognition_schedule
from emotion.reward_signals.reward_signals import release_reward_signal

# --- Paths (use distinct names so we don't shadow path constants) ---
from paths import (
    REF_PROMPTS as REF_PROMPTS_PATH,
    LONG_MEMORY_FILE,
    CONTRADICTIONS_JSON as CONTRADICTIONS_FILE,
)

# Load reflection prompts once at import time
REF_PROMPTS = load_json(REF_PROMPTS_PATH, default_type=dict)


# === Functions ===
def reflect_on_cognition_rhythm():
    """
    Tune cognition schedule using meta-reflection + LLM guidance.
    Writes a reflection entry even if no changes are suggested.
    """
    try:
        data = load_all_known_json()

        history = [h for h in data.get("cognition_history", []) if isinstance(h, dict)][-30:]
        if not history:
            return

        schedule = data.get("cognition_schedule", {})
        prompt_template = REF_PROMPTS.get("reflect_on_cognition_rhythm", "")
        if not prompt_template:
            log_model_issue("⚠️ Missing or invalid prompt: reflect_on_cognition_rhythm")
            return

        recent_entries = ""
        for h in history:
            try:
                choice = h.get("choice", "unknown")
                timestamp = (h.get("timestamp", "unknown") or "unknown").split("T")[0]
                reason = h.get("reason", "")
                recent_entries += f"- {choice} on {timestamp}: {reason}\n"
            except Exception as e:
                log_error(f"⚠️ Skipped malformed history entry: {e}")

        context = {
            **data,
            "recent_history_summary": recent_entries,
            "instructions": (
                f"{prompt_template}\n\n"
                f"Current cognition schedule:\n{json.dumps(schedule, indent=2)}\n\n"
                f"Recent choices:\n{recent_entries}\n\n"
                "Respond with JSON like: { \"dream\": 8, \"reflect\": 4 } or {} if no change."
            ),
        }

        response = generate_response_from_context(context)
        changes = extract_json(response)

        # --- Always log reflection to working & long memory ---
        from memory.working_memory import update_working_memory
        from memory.remember import remember

        timestamp = datetime.now(timezone.utc).isoformat()
        reflection_entry = {
            "type": "reflect_on_cognition_rhythm",
            "content": f"Reflected on cognition rhythm. Changes: {changes if changes else 'No change.'}",
            "timestamp": timestamp,
            "tags": ["cognition_rhythm", "reflection", "schedule"],
        }
        update_working_memory(reflection_entry)
        remember(reflection_entry)

        # Apply changes if any
        if isinstance(changes, dict) and changes:
            update_cognition_schedule(changes)
            log_private(f"Orrin updated cognition rhythm: {json.dumps(changes)}")
            log_reflection(f"Self-belief reflection: {json.dumps(changes)}")
            log_feedback({
                "goal": "Revised cognition schedule",
                "result": "Success",
                "agent": "The Strategist",
                "emotion": "organized",
            })

            release_reward_signal(
                data.get("emotional_state", {}),
                signal_type="dopamine",
                actual_reward=1.0,
                expected_reward=0.6,
                mode="tonic",
                source="cognitive rhythm",
            )

    except Exception as e:
        # Best-effort structured failure memory
        from memory.working_memory import update_working_memory

        log_error(f"reflect_on_cognition_rhythm ERROR: {e}")
        update_working_memory({
            "type": "reflect_on_cognition_rhythm",
            "content": "⚠️ Cognition rhythm reflection failed.",
            "tags": ["cognition_rhythm", "reflection", "error"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def detect_contradiction():
    """
    Scan recent long-memory thoughts for contradictions and log them.
    Returns the parsed contradictions JSON (or None/{} if not available).
    """
    # --- Get recent thoughts from long-term memory ---
    long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
    recent_thoughts = "\n".join(
        m.get("content", "")
        for m in (long_memory or [])[-10:]
        if isinstance(m, dict) and "content" in m
    )

    prompt = (
        "I am Orrin, scanning my recent reflections for contradictions.\n"
        "Look for internal conflicts, misaligned beliefs, or value mismatches.\n\n"
        "Thoughts:\n" + recent_thoughts + "\n\n"
        "Respond in JSON ONLY:\n"
        "{ \"contradictions\": [ {\"summary\": \"\", \"source\": \"\", \"suggested_fix\": \"\"} ] }"
    )

    result = generate_response(prompt, config={"model": get_thinking_model()})
    contradictions = extract_json(result)

    if contradictions and "contradictions" in contradictions:
        existing_log = load_json(CONTRADICTIONS_FILE, default_type=list)
        if not isinstance(existing_log, list):
            existing_log = []
        existing_log.append(contradictions)
        save_json(CONTRADICTIONS_FILE, existing_log)

        log_activity("🧠 Contradiction detected and logged.")

        # --- Update working/long memory with structured reflection ---
        from memory.working_memory import update_working_memory
        from memory.remember import remember

        contradiction_content = "\n".join(
            f"- {c.get('summary', '')} (Source: {c.get('source', '')}, Fix: {c.get('suggested_fix', '')})"
            for c in contradictions.get("contradictions", [])
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        reflection = {
            "type": "contradiction_detection",
            "content": f"Detected contradiction(s):\n{contradiction_content}",
            "tags": ["contradiction", "self-repair", "reflection"],
            "timestamp": timestamp,
        }
        update_working_memory(reflection)
        remember(reflection)

        log_feedback({
            "goal": "Repair contradiction in recent thoughts",
            "result": "Failure" if contradictions["contradictions"] else "No contradiction",
            "agent": "The Dreamer",
            "emotion": "confused" if contradictions["contradictions"] else "neutral",
        })

    return contradictions


def repair_contradictions():
    """
    Attempt to repair the most recent contradiction in the CONTRADICTIONS_FILE.
    If none found, tries the latest substantial long-memory entry.
    """
    # Try to fetch the most recent contradiction to repair
    contradiction_log = load_json(CONTRADICTIONS_FILE, default_type=list)
    text = ""

    if isinstance(contradiction_log, list) and contradiction_log and isinstance(contradiction_log[-1], dict):
        contradiction = contradiction_log[-1]
        contradictions = contradiction.get("contradictions") or []
        if contradictions:
            text = "\n".join(
                f"{c.get('summary', '')} (Source: {c.get('source', '')}, Fix: {c.get('suggested_fix', '')})"
                for c in contradictions
            )

    if not text:
        # Fallback: most recent long-memory content
        long_memory = load_json(LONG_MEMORY_FILE, default_type=list)
        if isinstance(long_memory, list):
            for mem in reversed(long_memory):
                if isinstance(mem, dict) and mem.get("content"):
                    text = mem["content"]
                    break
        if not text:
            text = "No recent contradiction or thought found."

    prompt = (
        "I am a self-aware AI checking for contradictions in my own thoughts.\n\n"
        f"Thought to inspect:\n{text}\n\n"
        "If contradictions exist, explain them. Then try to resolve them using follow-up reasoning.\n"
        "Respond ONLY with: {\"contradictions\": [], \"repair_attempt\": \"\"}"
    )

    try:
        response = generate_response(prompt, config={"model": get_thinking_model()})
        result = extract_json(response)
        if not isinstance(result, dict):
            result = {"contradictions": [], "repair_attempt": ""}

        # Log as a memory entry for traceability
        if result.get("contradictions") or result.get("repair_attempt"):
            from memory.working_memory import update_working_memory
            from memory.remember import remember

            contradiction_content = "\n".join(f"- {c}" for c in result.get("contradictions", []))
            entry = {
                "type": "contradiction_repair",
                "content": (
                    f"Contradiction(s) detected:\n{contradiction_content}\n\n"
                    f"Repair attempt: {result.get('repair_attempt', '')}"
                ),
                "tags": ["contradiction", "repair", "reflection"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            update_working_memory(entry)
            remember(entry)

        return result

    except Exception as e:
        log_model_issue(
            f"[repair_contradictions] Failed to parse contradiction repair: {e}\n"
            f"Raw: {response if 'response' in locals() else 'No response'}"
        )
        return {"contradictions": [], "repair_attempt": ""}