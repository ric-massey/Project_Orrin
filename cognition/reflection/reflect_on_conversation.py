import os
import json
from datetime import datetime, timezone

from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from paths import CONTEXT, LOGS_DIR  # <- use paths, not hardcoded folder

CONVERSATION_REFLECTION_LOG = os.path.join(LOGS_DIR, "conversation_reflection.log")

def reflect_on_conversation_patterns():
    try:
        # Load conversation context safely
        try:
            with open(CONTEXT, "r", encoding="utf-8") as f:
                context = json.load(f)
        except FileNotFoundError:
            log_private("🧠 No CONTEXT file found; skipping conversation pattern reflection.")
            return
        except Exception as e:
            log_error(f"❌ Failed to read CONTEXT: {e}")
            return

        history = context.get("conversation_history", [])
        if not isinstance(history, list):
            log_error("❌ conversation_history is not a list in CONTEXT.")
            return

        history = history[-15:]
        if not history:
            log_private("🧠 No recent conversation data for pattern reflection.")
            return

        # Build a compact summary (handles non-dict entries gracefully)
        lines = []
        for m in history:
            if isinstance(m, dict):
                tone = m.get("tone", "unknown")
                text = str(m.get("thought", "") or m.get("content", ""))[:100]
                lines.append(f"- {tone} | {text}")
            else:
                # If a non-dict sneaks in, just stringify it
                lines.append(f"- unknown | {str(m)[:100]}")
        summary = "\n".join(lines)

        prompt = (
            "I am Orrin, an AGI reflecting on my recent conversational behavior.\n\n"
            "Here are my last conversation entries (tone and content):\n"
            f"{summary}\n\n"
            "Reflect:\n"
            "- What tone do I tend to use?\n"
            "- Am I hesitating too often?\n"
            "- What intention drives my speech?\n"
            "- Do I sound human? Honest? Robotic?\n"
            "- Should I speak more or less?\n"
            "- Suggest 1 improvement.\n\n"
            "Respond in narrative form or bullet points."
        )

        reflection = generate_response(prompt, config={"model": get_thinking_model()})
        if reflection and isinstance(reflection, str) and reflection.strip():
            log_private(f"🧠 Conversation Pattern Reflection:\n{reflection}")

            # Ensure log directory exists and append
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(CONVERSATION_REFLECTION_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now(timezone.utc).isoformat()}]\n{reflection.strip()}\n")

            log_reflection(f"Self-belief reflection: {reflection.strip()}")
        else:
            log_private("🧠 No reflection generated for conversation pattern.")

    except Exception as e:
        log_error(f"❌ reflect_on_conversation_patterns() error: {e}")