import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Import functions under test
from memory.chat_log import (
    _is_noise,
    get_user_input,
    log_user_message,
    log_dialogue_pair,
    log_raw_user_input,
    summarize_chat_to_long_memory,
)

class ChatLogModuleTests(unittest.TestCase):
    def test_is_noise_detection(self):
        self.assertTrue(_is_noise(" — "))
        self.assertTrue(_is_noise("--"))
        self.assertFalse(_is_noise("Hello"))

    def test_get_user_input_reads_and_clears_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpfile = Path(tmpdir) / "user_input.txt"
            tmpfile.write_text("Hi", encoding="utf-8")

            import paths
            original_user_input = paths.USER_INPUT
            paths.USER_INPUT = str(tmpfile)
            try:
                content = get_user_input()
                self.assertEqual(content, "Hi")
                self.assertEqual(tmpfile.read_text(encoding="utf-8"), "")
            finally:
                paths.USER_INPUT = original_user_input

    def test_log_user_message_appends_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_path = Path(tmpdir) / "chat_log.json"

            import paths
            original_chat_log_file = paths.CHAT_LOG_FILE
            paths.CHAT_LOG_FILE = str(chat_path)
            try:
                log_user_message("Hello")
                data = json.loads(chat_path.read_text(encoding="utf-8"))
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["speaker"], "user")
                self.assertEqual(data[0]["content"], "Hello")
            finally:
                paths.CHAT_LOG_FILE = original_chat_log_file

    def test_log_dialogue_pair_appends_both_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_path = Path(tmpdir) / "chat_log.json"

            import paths
            original_chat_log_file = paths.CHAT_LOG_FILE
            paths.CHAT_LOG_FILE = str(chat_path)
            try:
                log_dialogue_pair("Hi", "Hello there", timestamp="2025-01-01T00:00:00Z")
                entries = json.loads(chat_path.read_text(encoding="utf-8"))
                self.assertEqual(len(entries), 2)
                self.assertEqual(entries[0]["speaker"], "user")
                self.assertEqual(entries[1]["speaker"], "orrin")
                self.assertEqual(entries[0]["timestamp"], "2025-01-01T00:00:00Z")
            finally:
                paths.CHAT_LOG_FILE = original_chat_log_file

    @patch("memory.chat_log.generate_response", return_value="Short summary")
    def test_summarize_chat_to_long_memory_creates_memory(self, _mock_generate):
        """Summarization adds one memory and trims the chat log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chat_log_path = Path(tmpdir) / "chat_log.json"
            long_memory_path = Path(tmpdir) / "long_memory.json"

            # 20 messages to meet the threshold
            messages = [{"content": f"msg {i}", "emotion": "neutral"} for i in range(20)]
            chat_log_path.write_text(json.dumps(messages), encoding="utf-8")
            long_memory_path.write_text("[]", encoding="utf-8")

            import paths
            original_chat = paths.CHAT_LOG_FILE
            original_long = paths.LONG_MEMORY_FILE
            paths.CHAT_LOG_FILE = str(chat_log_path)
            paths.LONG_MEMORY_FILE = str(long_memory_path)
            try:
                summarize_chat_to_long_memory(
                    cycle_count=10,
                    chat_log_file=str(chat_log_path),
                    long_memory_file=str(long_memory_path),
                )

                # Verify long memory gained one entry
                long_memory = json.loads(long_memory_path.read_text(encoding="utf-8"))
                self.assertEqual(len(long_memory), 1)
                self.assertEqual(long_memory[0]["content"], "Short summary")

                # Verify chat log trimmed to 10
                trimmed_chat = json.loads(chat_log_path.read_text(encoding="utf-8"))
                self.assertEqual(len(trimmed_chat), 10)
            finally:
                paths.CHAT_LOG_FILE = original_chat
                paths.LONG_MEMORY_FILE = original_long

if __name__ == "__main__":
    unittest.main()