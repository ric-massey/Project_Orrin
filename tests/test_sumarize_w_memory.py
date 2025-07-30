import unittest
from unittest.mock import patch

# Adjust this import to match your project structure
import memory.sumarize_w_memory as swwm

class SummarizeWorkingMemoryTests(unittest.TestCase):
    @patch("memory.sumarize_w_memory.update_long_memory")
    @patch("memory.sumarize_w_memory.get_embedding", return_value=[0.0])
    @patch("memory.sumarize_w_memory.detect_emotion", return_value="neutral")
    @patch("memory.sumarize_w_memory.summarize_memories", return_value="summary text")
    def test_summary_promotes_entry(
        self, mock_summarize, mock_emotion, mock_embedding, mock_update
    ):
        """Ensure that summarising working memory generates a summary entry and calls update_long_memory."""
        memories = [
            {"id": "1", "content": "Thought A", "referenced": 1, "pin": False, "event_type": "thought", "decay": 1.0, "recall_count": 0},
            {"id": "2", "content": "Thought B", "referenced": 0, "pin": True,  "event_type": "event", "decay": 0.8, "recall_count": 2},
        ]
        swwm.summarize_and_promote_working_memory(memories)
        # update_long_memory should have been called once with the summary entry
        self.assertTrue(mock_update.called)
        # Inspect the summary entry passed to update_long_memory
        summary_entry = mock_update.call_args[0][0]
        self.assertIn("content", summary_entry)
        self.assertIn("decay", summary_entry)
        self.assertEqual(summary_entry["referenced"], 1)  # sum of 'referenced' fields
        self.assertTrue(summary_entry["pin"])  # because one pin exists

if __name__ == "__main__":
    unittest.main()