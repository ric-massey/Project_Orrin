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
        # --- PATCH: Filter empty/dash input here ---
        if not user_input or user_input in {"—", "-", "--", "---"}:
            return ""  # Explicitly return empty string to skip
        return user_input
    except Exception:
        return ""
    
def append_to_json(filepath, obj):
    import json
    import os

    # If file does not exist, create and write list
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            json.dump([obj], f, indent=2)
        return

    # If file exists, try to load and append
    try:
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
            except Exception:
                data = []
        data.append(obj)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to append to {filepath}: {e}")

def log_raw_user_input(entry):
    """
    Append user and Orrin dialogue entries separately to chat log JSON.
    Accepts either a string (user-only) or a dict with user/orrin fields.
    """
    try:
        # -- Filter dash/empty input (user OR orrin) --
        if isinstance(entry, str):
            if not entry.strip() or entry.strip() in {"—", "-", "--", "---"}:
                return  # Don't log empty/dash messages
            user_entry = {
                "speaker": "user",
                "content": entry,
                "emotion": detect_emotion(entry),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            append_to_json(CHAT_LOG_FILE, user_entry)
        elif isinstance(entry, dict) and "user" in entry and "orrin" in entry:
            if (not entry["user"].strip() or entry["user"].strip() in {"—", "-", "--", "---"}) and \
               (not entry["orrin"].strip() or entry["orrin"].strip() in {"(no reply)"}):
                return  # Don't log junk exchanges
            # Optionally, you can log only one side if you want
            user_entry = {
                "speaker": "user",
                "content": entry["user"],
                "emotion": detect_emotion(entry["user"]),
                "timestamp": entry.get("timestamp") or datetime.now(timezone.utc).isoformat()
            }
            orrin_entry = {
                "speaker": "orrin",
                "content": entry["orrin"],
                "emotion": detect_emotion(entry["orrin"]),
                "timestamp": entry.get("timestamp") or datetime.now(timezone.utc).isoformat()
            }
            # Only log meaningful stuff
            if user_entry["content"].strip() and user_entry["content"].strip() not in {"—", "-", "--", "---"}:
                append_to_json(CHAT_LOG_FILE, user_entry)
            if orrin_entry["content"].strip() and orrin_entry["content"].strip().lower() != "(no reply)":
                append_to_json(CHAT_LOG_FILE, orrin_entry)
        else:
            log_error("Invalid entry format for log_raw_user_input.")
    except Exception as e:
        log_error(f"Error logging user input: {e}")

def summarize_chat_to_long_memory(cycle_count, chat_log_file, long_memory_file):
    """
    Every N cycles, summarize recent chat log entries into long-term memory.
    If 20+ messages exist, summarize and trim the oldest 10.
    """
    if cycle_count % 5 != 0:
        return

    try:
        chat_log = load_json(chat_log_file, default_type=list)
        if len(chat_log) < 20:
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

        # Optionally, extract main emotion from all recent chats for summary
        from emotion.emotion import detect_emotion
        emotions = [entry.get("emotion") for entry in recent_chats if entry.get("emotion")]
        labels = []
        for e in emotions:
            if isinstance(e, dict):
                val = e.get("emotion", None)
                if val:
                    labels.append(val)
            elif isinstance(e, str):
                labels.append(e)
        emotion = max(set(labels), key=labels.count) if labels else "neutral"

        # Save summary to long-term memory with all schema fields
        long_memory = load_json(long_memory_file, default_type=list)
        new_memory = {
            "content": summary.strip(),
            "emotion": emotion,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "chat_summary",
            "agent": "orrin",
            "importance": 2,
            "priority": 2,
            "referenced": sum(entry.get("referenced", 0) for entry in recent_chats),
            "pin": False,
            "decay": 1.0,
            "recall_count": 0,
            "related_memory_ids": [entry.get("id") for entry in recent_chats if entry.get("id")],
        }
        long_memory.append(new_memory)
        save_json(long_memory_file, long_memory)

        # Trim the oldest 10 entries from chat log
        trimmed_log = chat_log[10:]
        save_json(chat_log_file, trimmed_log)

    except Exception as e:
        log_error(f"Error summarizing chat to long memory: {e}")
        
def wrap_text(text, width=85):
    import textwrap
    return "\n".join(textwrap.wrap(text, width=width))