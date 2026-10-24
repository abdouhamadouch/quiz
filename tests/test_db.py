import tempfile
import unittest
from pathlib import Path

import db


SAMPLE_QUESTIONS = [{
    "question": "Which is correct?",
    "options": ["went", "goed", "goes", "going"],
    "answer": 0,
    "explanation": "Go is irregular.",
}]


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp.name) / "quiz.sqlite3")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_saved_quiz_crud_and_owner_isolation(self):
        quiz_id = db.save_quiz(101, "English verbs", "Lesson text", SAMPLE_QUESTIONS, 30, "exam", "easy")
        self.assertEqual(db.get_quiz(quiz_id, 101)["questions"], SAMPLE_QUESTIONS)
        self.assertIsNone(db.get_quiz(quiz_id, 202))
        self.assertEqual(db.list_quizzes(101, search="verbs")[0]["id"], quiz_id)
        self.assertTrue(db.rename_quiz(quiz_id, 101, "Past tense"))
        self.assertEqual(db.get_quiz(quiz_id, 101)["title"], "Past tense")
        self.assertFalse(db.delete_quiz(quiz_id, 202))
        self.assertTrue(db.delete_quiz(quiz_id, 101))
        self.assertIsNone(db.get_quiz(quiz_id, 101))

    def test_copy_preserves_settings_and_questions(self):
        quiz_id = db.save_quiz(101, "English verbs", "Lesson text", SAMPLE_QUESTIONS, 45, "review_manual", "hard")
        copied_id = db.copy_quiz(quiz_id, 101)
        copied = db.get_quiz(copied_id, 101)
        self.assertEqual(copied["questions"], SAMPLE_QUESTIONS)
        self.assertEqual(copied["seconds"], 45)
        self.assertEqual(copied["mode"], "review_manual")
        self.assertEqual(copied["difficulty"], "hard")

    def test_group_draft_survives_database_reload(self):
        quiz_id = db.save_quiz(101, "English verbs", "Lesson text", SAMPLE_QUESTIONS)
        quiz = db.get_quiz(quiz_id, 101)
        db.save_group_draft(-1001, 101, quiz)
        loaded = db.get_group_drafts()
        self.assertEqual(loaded[-1001]["owner_id"], 101)
        self.assertEqual(loaded[-1001]["quiz"]["id"], quiz_id)
        db.delete_group_draft(-1001)
        self.assertNotIn(-1001, db.get_group_drafts())

    def test_per_quiz_leaderboard_is_saved(self):
        quiz_id = db.save_quiz(101, "English verbs", "Lesson text", SAMPLE_QUESTIONS)
        db.save_quiz_results(-1001, quiz_id, {
            101: {"name": "Learner", "points": 10, "correct": 1, "answered": 1}
        })
        rows = db.quiz_leaderboard(-1001, quiz_id)
        self.assertEqual(rows[0]["name"], "Learner")
        self.assertEqual(rows[0]["points"], 10)

    def test_init_is_safe_to_run_more_than_once(self):
        db.init_db()
        db.init_db()


if __name__ == "__main__":
    unittest.main()
