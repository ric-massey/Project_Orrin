# test_sumarize_w_memory.py
import unittest
from unittest.mock import patch

# Adjust this import to match your project structure
import memory.summarize_w_memory as swwm

class SummarizeWorkingMemoryTests(unittest.TestCase):
    @patch("memory.summarize_w_memory.update_long_memory")
    @patch("memory.summarize_w_memory.get_embedding", return_value=[0.0])
    @patch("memory.summarize_w_memory.detect_emotion", return_value="neutral")
    @patch("memory.summarize_w_memory.summarize_memories", return_value="summary text")
    def test_summary_promotes_entry(
        self, mock_summarize, mock_emotion, mock_embedding, mock_update
    ):
        """Ensure that summarising working memory generates a summary entry and calls update_long_memory."""
        memories = [
            {"id": "1", "content": "Thought A", "referenced": 1, "pin": False, "event_type": "thought", "decay": 1.0, "recall_count": 0},
            {"id": "2", "content": "Thought B", "referenced": 0, "pin": True,  "event_type": "event",  "decay": 0.8, "recall_count": 2},
        ]

        swwm.summarize_and_promote_working_memory(memories)

        # update_long_memory should have been called exactly once
        mock_update.assert_called_once()

        # Inspect the summary entry passed to update_long_memory
        summary_entry = mock_update.call_args[0][0]

        self.assertIn("content", summary_entry)
        self.assertIn("decay", summary_entry)
        self.assertEqual(summary_entry["event_type"], "summary")
        self.assertEqual(summary_entry["referenced"], 1)  # sum of 'referenced' fields (1 + 0)
        self.assertTrue(summary_entry["pin"])             # because one pin exists
        self.assertEqual(sorted(summary_entry["related_memory_ids"]), ["1", "2"])
        self.assertEqual(summary_entry["embedding"], [0.0])   # from patched get_embedding
        self.assertEqual(summary_entry["emotion"], "neutral") # from patched detect_emotion

if __name__ == "__main__":
    unittest.main()