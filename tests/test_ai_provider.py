import unittest
from ai_provider import validate_questions, _parse_json

class QuestionValidationTests(unittest.TestCase):
    def test_valid_question_is_kept(self):
        data = {"questions": [{"question": "What is the past tense of go?", "options": ["went", "goed", "goes", "going"], "answer": 0, "explanation": "Go is irregular."}]}
        self.assertEqual(len(validate_questions(data, 5)), 1)

    def test_duplicate_options_are_rejected(self):
        data = {"questions": [{"question": "Pick one", "options": ["A", "A", "B", "C"], "answer": 0}]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_bad_answer_index_is_rejected(self):
        data = {"questions": [{"question": "Pick one", "options": ["A", "B", "C", "D"], "answer": 4}]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_json_fence_is_parsed(self):
        self.assertEqual(_parse_json('{"questions": []}'), {"questions": []})

if __name__ == "__main__":
    unittest.main()
