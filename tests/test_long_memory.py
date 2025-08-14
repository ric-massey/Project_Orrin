# test_long_memory.py
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import memory.long_memory as longmem
import memory.remember as remember_mod  # so we can patch its LONG_MEMORY_FILE separately
from memory.remember import remember

class LongMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.long_path = Path(self.tempdir.name) / "long_memory.json"
        self.priv_path = Path(self.tempdir.name) / "private.txt"

        self.long_path.write_text("[]", encoding="utf-8")
        self.priv_path.write_text("", encoding="utf-8")

        # Save originals and patch both modules that reference the path
        self._orig_long_longmem = longmem.LONG_MEMORY_FILE
        self._orig_priv_longmem = longmem.PRIVATE_THOUGHTS_FILE
        longmem.LONG_MEMORY_FILE = str(self.long_path)
        longmem.PRIVATE_THOUGHTS_FILE = str(self.priv_path)

        self._orig_long_remember = remember_mod.LONG_MEMORY_FILE
        remember_mod.LONG_MEMORY_FILE = str(self.long_path)

    def tearDown(self):
        longmem.LONG_MEMORY_FILE = self._orig_long_longmem
        longmem.PRIVATE_THOUGHTS_FILE = self._orig_priv_longmem
        remember_mod.LONG_MEMORY_FILE = self._orig_long_remember
        self.tempdir.cleanup()

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_update_long_memory_adds_entry(self, mock_emotion, mock_embed):
        longmem.update_long_memory("My first memory")
        data = json.loads(self.long_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "My first memory")

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_update_long_memory_skips_duplicates(self, mock_emotion, mock_embed):
        longmem.update_long_memory("Repeat me")
        longmem.update_long_memory("Repeat me")
        data = json.loads(self.long_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)

    @patch("memory.remember.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.remember.detect_emotion", return_value="neutral")
    def test_remember_adds_entry(self, mock_emotion, mock_embed):
        remember("An interesting event")
        data = json.loads(self.long_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "An interesting event")

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_prune_long_memory(self, mock_emotion, mock_embed):
        for i in range(8):
            longmem.update_long_memory(f"Mem {i}")
        longmem.prune_long_memory(max_total=5)
        data = json.loads(self.long_path.read_text(encoding="utf-8"))
        # 5 kept, plus optionally a summary entry
        self.assertTrue(5 <= len(data) <= 6)

    @patch("memory.long_memory.get_embedding", return_value=[0.0, 0.0])
    @patch("memory.long_memory.detect_emotion", return_value="neutral")
    def test_reevaluate_memory_significance(self, mock_emotion, mock_embed):
        longmem.update_long_memory("Lesson: study hard", importance=3, priority=3)
        longmem.update_long_memory("Casual note", importance=1, priority=1)
        longmem.reevaluate_memory_significance()
        data = json.loads(self.long_path.read_text(encoding="utf-8"))
        for mem in data:
            self.assertIn("effectiveness_score", mem)

if __name__ == "__main__":
    unittest.main()