# test_working_memory.py
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# System under test
import memory.working_memory as wm
from paths import WORKING_JSON  # <-- import the test filename constant

class UpdateWorkingMemoryTests(unittest.TestCase):
    def setUp(self):
        # Use a temporary file for working memory
        self.tempdir = tempfile.TemporaryDirectory()
        self.mem_path = Path(self.tempdir.name) / WORKING_JSON
        self.mem_path.write_text("[]", encoding="utf-8")

        # Override the module’s WORKING_MEMORY_FILE constant
        self._orig_path = wm.WORKING_MEMORY_FILE
        wm.WORKING_MEMORY_FILE = str(self.mem_path)

    def tearDown(self):
        # Restore the original constant and clean up
        wm.WORKING_MEMORY_FILE = self._orig_path
        self.tempdir.cleanup()

    @patch("memory.working_memory.get_embedding", return_value=[0.0])
    @patch("memory.working_memory.detect_emotion", return_value="neutral")
    def test_add_single_entry(self, mock_emotion, mock_embedding):
        """A new string entry should be added to working memory."""
        wm.update_working_memory("hello")
        data = json.loads(self.mem_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "hello")
        self.assertEqual(data[0]["emotion"], "neutral")
        self.assertEqual(data[0]["embedding"], [0.0])

    @patch("memory.working_memory.get_embedding", return_value=[0.0])
    @patch("memory.working_memory.detect_emotion", return_value="neutral")
    @patch("memory.working_memory.summarize_and_promote_working_memory")
    def test_prune_and_promote(self, mock_summary, mock_emotion, mock_embedding):
        """
        When working memory exceeds MAX_WORKING_LOGS, older non-pinned entries should be
        summarised and promoted.
        """
        # Temporarily reduce MAX_WORKING_LOGS to force pruning
        original_max = wm.MAX_WORKING_LOGS
        wm.MAX_WORKING_LOGS = 3
        try:
            for i in range(5):
                wm.update_working_memory(f"msg {i}")
            data = json.loads(self.mem_path.read_text(encoding="utf-8"))
            self.assertLessEqual(len(data), 3)
            self.assertTrue(mock_summary.called)
        finally:
            wm.MAX_WORKING_LOGS = original_max

if __name__ == "__main__":
    unittest.main()