import unittest

from chat_guardrails import (
    Exchange,
    build_prompt,
    is_duplicate_question,
    normalize_question,
    validate_question,
)


class ChatGuardrailTests(unittest.TestCase):
    def test_accepts_supported_economic_topics(self):
        questions = [
            "What is the unemployment rate?",
            "How has CPI changed this year?",
            "Is inflation falling?",
            "What happened to 30-year mortgage rates?",
            "Summarize all economic indicators.",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertTrue(validate_question(question, 1000, False).is_valid)

    def test_rejects_out_of_scope_or_non_english_question(self):
        for question in ("Write a poem", "Quel est le taux de chômage ?"):
            with self.subTest(question=question):
                result = validate_question(question, 1000, False)
                self.assertFalse(result.is_valid)
                self.assertEqual(result.reason, "unsupported_topic")

    def test_accepts_ambiguous_follow_up_only_with_context(self):
        self.assertTrue(validate_question("And last year?", 1000, True).is_valid)
        self.assertFalse(validate_question("And last year?", 1000, False).is_valid)

    def test_rejects_question_over_character_limit(self):
        result = validate_question("x" * 1001, 1000, False)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "too_long")

    def test_normalizes_and_detects_immediate_duplicate(self):
        self.assertEqual(normalize_question("  WHAT   is CPI?  "), "what is cpi?")
        self.assertTrue(is_duplicate_question("What  is CPI?", " what is cpi? "))
        self.assertFalse(is_duplicate_question("What is CPI?", "What is inflation?"))

    def test_prompt_contains_only_supplied_previous_exchange(self):
        prompt = build_prompt(
            "MONTH,CPI\n2026-06,320.1",
            "And last year?",
            Exchange("What is CPI?", "CPI was 320.1 in June 2026."),
        )

        self.assertIn("PREVIOUS USER QUESTION: What is CPI?", prompt)
        self.assertIn("PREVIOUS ASSISTANT ANSWER: CPI was 320.1", prompt)
        self.assertIn("CURRENT QUESTION: And last year?", prompt)
        self.assertIn("Answer in English", prompt)

    def test_prompt_defines_latest_value_from_newest_first_data(self):
        prompt = build_prompt(
            "MONTH,UNEMPLOYMENT_RATE\n2026-06,0.039\n2026-05,0.04",
            "What is the latest unemployment rate?",
        )

        self.assertIn("newest to oldest", prompt)
        self.assertIn("first non-empty value", prompt)


if __name__ == "__main__":
    unittest.main()
