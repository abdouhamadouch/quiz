import unittest

from quiz_export import format_quiz_export, format_session_report


SAMPLE_QUESTIONS = [
    {
        "question": "Which is correct?",
        "options": ["went", "goed", "goes", "going"],
        "answer": 0,
        "explanation": "Go is irregular.",
    },
    {
        "question": "Choose the article.",
        "options": ["a", "an", "the", "no article"],
        "answer": 1,
        "explanation": "",
    },
]


class QuizExportTests(unittest.TestCase):
    def test_quiz_export_contains_all_options_correct_answer_and_explanation(self):
        result = format_quiz_export({
            "id": 7, "title": "English verbs", "questions": SAMPLE_QUESTIONS,
            "category": "Grammar", "difficulty": "easy", "seconds": 30, "mode": "exam",
        })
        self.assertIn("الاختبار #7: English verbs", result)
        self.assertIn("A. went", result)
        self.assertIn("D. going", result)
        self.assertIn("الإجابة الصحيحة: A. went", result)
        self.assertIn("Go is irregular.", result)
        self.assertIn("الإجابة الصحيحة: B. an", result)
        self.assertEqual(result.count("السؤال "), 2)

    def test_session_report_includes_results_and_answer_key(self):
        result = format_session_report({
            "quiz_title": "Grammar test",
            "mode": "exam",
            "questions": SAMPLE_QUESTIONS,
            "scores": {
                10: {"name": "Learner A", "points": 10, "correct": 1, "answered": 2},
                11: {"name": "Learner B", "points": 20, "correct": 2, "answered": 2},
            },
        })
        self.assertLess(result.index("Learner B"), result.index("Learner A"))
        self.assertIn("20 نقطة (2/2 صحيحة)", result)
        self.assertIn("السؤال 1: Which is correct?", result)
        self.assertIn("الإجابة الصحيحة: A. went", result)
        self.assertIn("Go is irregular.", result)

    def test_review_report_has_answer_key_without_competition_scores(self):
        result = format_session_report({
            "quiz_title": "Review",
            "mode": "review_manual",
            "questions": SAMPLE_QUESTIONS,
            "scores": {},
        })
        self.assertIn("مفتاح إجابات المراجعة", result)
        self.assertIn("الإجابة الصحيحة: B. an", result)
        self.assertNotIn("النتائج النهائية", result)


if __name__ == "__main__":
    unittest.main()
