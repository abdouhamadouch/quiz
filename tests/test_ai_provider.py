import unittest
from unittest.mock import patch

import ai_provider
from ai_provider import validate_questions, _parse_json, generate_questions


def question(text="Pick one", options=None, answer=0):
    return {
        "question": text,
        "options": options or ["A", "B", "C", "D"],
        "answer": answer,
        "explanation": "Explanation",
    }


class QuestionValidationTests(unittest.TestCase):
    def test_valid_question_is_kept(self):
        data = {"questions": [question("What is the past tense of go?", ["went", "goed", "goes", "going"])]}
        self.assertEqual(len(validate_questions(data, 5)), 1)

    def test_duplicate_options_are_rejected(self):
        data = {"questions": [question(options=["A", "A", "B", "C"])]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_whitespace_only_option_difference_is_rejected(self):
        data = {"questions": [question(options=["New York", "New  York", "Paris", "Rome"])]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_bad_answer_index_is_rejected(self):
        data = {"questions": [question(answer=4)]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_boolean_answer_is_rejected(self):
        data = {"questions": [question(answer=True)]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_fractional_answer_index_is_rejected(self):
        data = {"questions": [question(answer=1.5)]}
        self.assertEqual(validate_questions(data, 1), [])

    def test_duplicate_questions_are_removed(self):
        data = {"questions": [question("Same?"), question(" same? ")]}
        self.assertEqual(len(validate_questions(data, 5)), 1)

    def test_json_fence_is_parsed(self):
        self.assertEqual(_parse_json('```json\n{"questions": []}\n```'), {"questions": []})

    def test_provider_failover_when_first_provider_returns_too_few(self):
        ai_provider._preferred = "groq"
        one = {"questions": [question("One?")]}
        two = {"questions": [question("One?"), question("Two?")]}
        with patch("ai_provider._groq", return_value=one), patch("ai_provider._gemini", return_value=two):
            questions, provider = generate_questions("source", 2)
        self.assertEqual(provider, "GEMINI")
        self.assertEqual(len(questions), 2)

    def test_both_providers_must_return_requested_count(self):
        ai_provider._preferred = "groq"
        one = {"questions": [question("One?")]}
        with patch("ai_provider._groq", return_value=one), patch("ai_provider._gemini", return_value=one):
            with self.assertRaises(RuntimeError):
                generate_questions("source", 2)

    def test_provider_error_details_are_not_exposed(self):
        ai_provider._preferred = "groq"
        with patch("ai_provider._groq", side_effect=RuntimeError("secret=TEST_KEY")), patch(
            "ai_provider._gemini", side_effect=RuntimeError("secret=TEST_KEY")
        ):
            with self.assertRaises(RuntimeError) as caught:
                generate_questions("source", 1)
        self.assertNotIn("TEST_KEY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
