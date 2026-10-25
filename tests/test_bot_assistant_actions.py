import unittest

from bot import _assistant_result_keyboard


class AssistantQuizActionKeyboardTests(unittest.TestCase):
    def test_each_quiz_offers_play_preview_copy_and_delete(self):
        keyboard = _assistant_result_keyboard([
            {"id": 7, "seconds": 30, "mode": "exam", "title": "Grammar"},
        ]).inline_keyboard

        callbacks = [button.callback_data for row in keyboard for button in row]
        self.assertEqual(len(keyboard), 2)
        self.assertIn("startprivate:7:30:exam", callbacks)
        self.assertIn("assistant:preview:7", callbacks)
        self.assertIn("assistant:copy:7", callbacks)
        self.assertIn("assistant:delete:7", callbacks)

    def test_keyboard_stays_compact_for_long_search_results(self):
        rows = [
            {"id": quiz_id, "seconds": 20, "mode": "exam"}
            for quiz_id in range(1, 10)
        ]
        keyboard = _assistant_result_keyboard(rows).inline_keyboard
        self.assertEqual(len(keyboard), 8)
        callbacks = [button.callback_data for row in keyboard for button in row]
        self.assertIn("assistant:preview:4", callbacks)
        self.assertNotIn("assistant:preview:5", callbacks)


if __name__ == "__main__":
    unittest.main()
