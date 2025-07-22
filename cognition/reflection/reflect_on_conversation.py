import json
from datetime import datetime, timezone
from utils.generate_response import generate_response, get_thinking_model
from utils.log import log_private, log_error
from utils.log_reflection import log_reflection
from paths import CONTEXT

def reflect_on_conversation_patterns():
    try:
        context = json.load(open(CONTEXT))
        history = context.get("conversation_history", [])[-15:]

        if not history:
            log_private("🧠 No recent conversation data for pattern reflection.")
            return

        summary = "\n".join(
            f"- {m.get('tone', 'unknown')} | {m.get('thought', '')[:100]}"
            for m in history
        )

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
        if reflection:
            log_private(f"🧠 Conversation Pattern Reflection:\n{reflection}")
            with open("logs/conversation_reflection.log", "a") as f:
                f.write(f"\n[{datetime.now(timezone.utc)}]\n{reflection}\n")
            log_reflection(f"Self-belief reflection: {reflection.strip()}")
        else:
            log_private("🧠 No reflection generated for conversation pattern.")

    except Exception as e:
        log_error(f"❌ reflect_on_conversation_patterns() error: {e}")