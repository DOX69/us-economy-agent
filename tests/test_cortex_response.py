import unittest

from src.utils.cortex_response import extract_message_content


class ExtractMessageContentTests(unittest.TestCase):
    def test_rejects_error_message_instead_of_treating_it_as_analyst_content(self):
        with self.assertRaisesRegex(RuntimeError, "Semantic View.*does not exist"):
            extract_message_content(
                {"message": "Semantic View 'MISSING' does not exist or not authorized."}
            )


if __name__ == "__main__":
    unittest.main()
