import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Import the functions you want to test
import memory.long_memory as longmem  # adjust this import to match your package layout

class LongMemoryTests(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and override file paths
        self.tempdir = tempfile.TemporaryDirectory()
        self.long_path = Path(self.tempdir.name) / "long.json"
        self.priv_path = Path(self.tempdir.name) / "private.txt"

        # Initialise empty files
        self.long_path.write_text("[]")
        self.priv_path.write_text("")
        # Store original constants and override them
        self._original_long = longmem.LONG_MEMORY_FILE
        self._original_private = longmem.PRIVATE_THOUGHTS_FILE
        longmem.LONG_MEMORY_FILE = str(self.long_path)
        longmem.PRIVATE_THOUGHTS_FILE = str(self.priv_path)

    def tearDown(self):
        # Restore the original constants and clean up
        longmem.LONG_MEMORY_FILE = self._original_long
        longmem.PRIVATE_THOUGHTS_FILE = self._original_private
        self.tempdir.cleanup()

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_update_long_memory_adds_entry(self, mock_emotion, mock_embed):
        """update_long_memory should append a new entry when it isn't a duplicate."""
        longmem.update_long_memory("My first memory")
        data = json.loads(self.long_path.read_text())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "My first memory")

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_update_long_memory_skips_duplicates(self, mock_emotion, mock_embed):
        """update_long_memory should not add a duplicate within the DUPLICATE_WINDOW."""
        longmem.update_long_memory("Repeat me")
        longmem.update_long_memory("Repeat me")  # duplicate
        data = json.loads(self.long_path.read_text())
        self.assertEqual(len(data), 1)  # still one entry

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_remember_adds_entry(self, mock_emotion, mock_embed):
        """remember should append a new entry to long-term memory."""
        longmem.remember("An interesting event")
        data = json.loads(self.long_path.read_text())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "An interesting event")

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_prune_long_memory(self, mock_emotion, mock_embed):
        """prune_long_memory should remove oldest entries and summarise them if over capacity."""
        # Insert more than MAX_LONG_MEMORY entries, but for test set a small max_total
        # We'll set max_total=5 to force pruning
        for i in range(8):
            longmem.update_long_memory(f"Mem {i}")
        longmem.prune_long_memory(max_total=5)
        data = json.loads(self.long_path.read_text())
        # After pruning down to 5, there may be a summary memory appended
        self.assertTrue(len(data) <= 6)  # 5 kept plus optional summary

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_reevaluate_memory_significance(self, mock_emotion, mock_embed):
        """reevaluate_memory_significance should update effectiveness_score on entries."""
        longmem.update_long_memory("Lesson: study hard", importance=3, priority=3)
        longmem.update_long_memory("Casual note", importance=1, priority=1)
        longmem.reevaluate_memory_significance()
        data = json.loads(self.long_path.read_text())
        # Each entry should now have an 'effectiveness_score' field
        for mem in data:
            self.assertIn("effectiveness_score", mem)

if __name__ == "__main__":
    unittest.main()