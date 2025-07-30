from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from emotion.emotion import detect_emotion
import paths
from utils.append import append_to_json
from utils.generate_response import generate_response
from utils.json_utils import load_json, save_json
from utils.log import log_error

# Tokens that will cause an entry to be ignored when logging
_NOISE_TOKENS = {"—", "-", "--", "---"}


def get_user_input() -> str:
    """
    Read and clear the contents of USER_INPUT.

    Returns:
        A stripped string if the file contains meaningful input, or an empty string if
        the file is empty, missing, or contains only dash characters.
    """
    try:
        with open(paths.USER_INPUT, "r", encoding="utf-8") as f:
            content = f.read().strip()
        # Clear the file after reading
        with open(paths.USER_INPUT, "w", encoding="utf-8"):
            pass
        return "" if not content or content in _NOISE_TOKENS else content
    except Exception:
        return ""


def _is_noise(content: str) -> bool:
    """
    Return True if the content is empty or consists solely of noise tokens.
    """
    stripped = content.strip()
    return not stripped or stripped in _NOISE_TOKENS


def _create_chat_entry(
    speaker: str, content: str, timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Construct a chat log entry with speaker, content, detected emotion, and timestamp.

    Args:
        speaker: The identifier for who is speaking (e.g. "user" or "orrin").
        content: The text content of the message.
        timestamp: Optional timestamp to assign; if not provided, the current UTC time is used.

    Returns:
        A dictionary representing the chat entry.
    """
    return {
        "speaker": speaker,
        "content": content,
        "emotion": detect_emotion(content),
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


def log_user_message(content: str) -> None:
    """
    Append a single user message to the chat log if it is not noise.
    """
    if not _is_noise(content):
        append_to_json(paths.CHAT_LOG_FILE, _create_chat_entry("user", content))


def log_dialogue_pair(user: str, orrin: str, timestamp: Optional[str] = None) -> None:
    """
    Append a user/orrin dialogue pair to the chat log.  Messages that are empty,
    consist only of dashes, or where Orrin’s reply is '(no reply)' are skipped.

    Args:
        user: The user’s message.
        orrin: The agent’s message.
        timestamp: Optional timestamp to apply to both messages.
    """
    if not _is_noise(user):
        append_to_json(paths.CHAT_LOG_FILE, _create_chat_entry("user", user, timestamp))
    orrin_stripped = orrin.strip()
    if orrin_stripped.lower() not in {"(no reply)", ""} and not _is_noise(orrin_stripped):
        append_to_json(paths.CHAT_LOG_FILE, _create_chat_entry("orrin", orrin_stripped, timestamp))


def log_raw_user_input(entry: Union[str, Dict[str, str]]) -> None:
    """
    Dispatch logging based on the type of entry provided.

    If `entry` is a string, it is logged as a single user message.
    If `entry` is a dict with 'user' and 'orrin' keys, it is logged as a dialogue pair.
    Any other format is ignored and reported to the error log.
    """
    try:
        if isinstance(entry, str):
            log_user_message(entry)
        elif isinstance(entry, dict) and {"user", "orrin"}.issubset(entry):
            log_dialogue_pair(entry["user"], entry["orrin"], entry.get("timestamp"))
        else:
            log_error("log_raw_user_input received invalid entry format.")
    except Exception as exc:
        log_error(f"Error logging user input: {exc}")


def summarize_chat_to_long_memory(
    cycle_count: int, chat_log_file: str, long_memory_file: str
) -> None:
    """
    Every 5 cycles, summarise the last 20 chat messages into a single long-term memory entry.

    A summary is generated from the most recent 20 chat log entries whenever
    `cycle_count` is divisible by 5 and at least 20 messages exist. Once summarised,
    the oldest 10 chat entries are trimmed from the log.

    Args:
        cycle_count: The current cycle number used to decide when to summarise.
        chat_log_file: Path to the JSON file containing the chat log.
        long_memory_file: Path to the JSON file where long-term memories are stored.
    """
    if cycle_count % 5:
        return

    try:
        chat_log: list[dict[str, Any]] = load_json(chat_log_file, default_type=list)
        if len(chat_log) < 20:
            return

        recent_chats = chat_log[-20:]
        chat_text = "\n".join(entry.get("content", "") for entry in recent_chats)
        prompt = (
            "Summarize the following recent conversation concisely and meaningfully, "
            "capturing main topics, emotions, and insights:\n\n"
            f"{chat_text}\n\nSummary:"
        )
        summary = generate_response(prompt)
        if not summary:
            return

        # Determine the most frequent emotion label across recent chats
        labels: list[str] = []
        for e in (entry.get("emotion") for entry in recent_chats):
            if isinstance(e, dict):
                if (val := e.get("emotion")):
                    labels.append(val)
            elif isinstance(e, str):
                labels.append(e)
        dominant_emotion = max(set(labels), key=labels.count) if labels else "neutral"

        # Build and save the new long-term memory record
        long_memory: list[dict[str, Any]] = load_json(long_memory_file, default_type=list)
        new_memory = {
            "content": summary.strip(),
            "emotion": dominant_emotion,
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

        # Trim the oldest 10 entries from the chat log
        save_json(chat_log_file, chat_log[10:])

    except Exception as exc:
        log_error(f"Error summarizing chat to long memory: {exc}")


def wrap_text(text: str, width: int = 85) -> str:
    """
    Return text wrapped to the specified width.  Useful for formatting console output or logs.
    """
    import textwrap
    return "\n".join(textwrap.wrap(text, width))