from datetime import datetime, timezone
from utils.json_utils import load_json, save_json
from utils.append import append_to_json
from emotion.emotion import detect_emotion
from utils.generate_response import generate_response
from utils.log import log_error
from paths import CHAT_LOG_FILE, USER_INPUT

def get_user_input(prompt="You: "):
    """
    Reads user input from USER_INPUT_FILE and clears it after reading.
    Returns stripped string, or "" if file is empty.
    """
    try:
        with open(USER_INPUT, "r", encoding="utf-8") as f:
            user_input = f.read().strip()
        # Clear file after reading
        with open(USER_INPUT, "w", encoding="utf-8") as f:
            f.write("")
        return user_input
    except Exception:
        return ""

def log_raw_user_input(user_input):
    """
    Append raw user input with timestamp and detected emotion to chat log JSON.
    """
    if user_input:
        try:
            append_to_json(CHAT_LOG_FILE, {
                "content": f"User: {user_input}",
                "emotion": detect_emotion(user_input),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            log_error(f"Error logging user input: {e}")

def summarize_chat_to_long_memory(cycle_count, chat_log_file, long_memory_file):
    """
    Every N cycles, summarize recent chat log entries into a condensed
    chat_summary memory in long term memory.
    """
    if cycle_count % 5 != 0:
        return

    try:
        chat_log = load_json(chat_log_file, default_type=list)
        if not chat_log:
            return

        recent_chats = chat_log[-20:]
        chat_text = "\n".join(entry.get("content", "") for entry in recent_chats)

        prompt = (
            "Summarize the following recent conversation concisely and meaningfully, "
            "capturing main topics, emotions, and insights:\n\n"
            f"{chat_text}\n\n"
            "Summary:"
        )

        summary = generate_response(prompt)
        if not summary:
            return

        long_memory = load_json(long_memory_file, default_type=list)
        new_memory = {
            "content": summary.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "chat_summary"
        }
        long_memory.append(new_memory)
        save_json(long_memory_file, long_memory)
    except Exception as e:
        log_error(f"Error summarizing chat to long memory: {e}")