import unittest

from app_config import AppSettings
from snowflake_service import (
    MONTHLY_DATA_SQL,
    ReservationStatus,
    complete_answer,
    reserve_daily_allowance,
)


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def collect(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def sql(self, query, params=None):
        self.calls.append((query, params))
        return FakeQuery(self.results.pop(0))


class SnowflakeServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings()

    def test_reserves_quota_and_counts_prompt_in_one_update(self):
        session = FakeSession([(1,)])

        result = reserve_daily_allowance(session, self.settings, "prompt")

        self.assertEqual(result.status, ReservationStatus.RESERVED)
        self.assertEqual(len(session.calls), 1)
        query, params = session.calls[0]
        self.assertIn("UPDATE ECON_AGENT_DB.ANALYTICS.APP_DAILY_QUOTA", query)
        self.assertIn("AI_COUNT_TOKENS('ai_complete'", query)
        self.assertEqual(params, [50, "mistral-large2", "prompt", 3000])

    def test_diagnoses_prompt_too_large_only_after_refused_update(self):
        session = FakeSession([(0,)], [(3001, 3)])

        result = reserve_daily_allowance(session, self.settings, "prompt")

        self.assertEqual(result.status, ReservationStatus.PROMPT_TOO_LARGE)
        self.assertEqual(len(session.calls), 2)

    def test_diagnoses_daily_limit_after_refused_update(self):
        session = FakeSession([(0,)], [(1200, 50)])

        result = reserve_daily_allowance(session, self.settings, "prompt")

        self.assertEqual(result.status, ReservationStatus.DAILY_LIMIT)

    def test_fails_closed_when_quota_table_is_unavailable(self):
        session = FakeSession(RuntimeError("database unavailable"))

        result = reserve_daily_allowance(session, self.settings, "prompt")

        self.assertEqual(result.status, ReservationStatus.UNAVAILABLE)

    def test_calls_ai_complete_with_configured_output_limit(self):
        session = FakeSession([("answer",)])

        answer = complete_answer(session, self.settings, "prompt")

        self.assertEqual(answer, "answer")
        query, params = session.calls[0]
        self.assertIn("AI_COMPLETE", query)
        self.assertEqual(params, ["mistral-large2", "prompt", 1000])

    def test_unwraps_json_string_returned_by_ai_complete(self):
        session = FakeSession([('"The latest rate is 4.0%."',)])

        answer = complete_answer(session, self.settings, "prompt")

        self.assertEqual(answer, "The latest rate is 4.0%.")

    def test_monthly_query_uses_latest_non_null_values_and_24_months(self):
        self.assertIn("MAX_BY(CPI", MONTHLY_DATA_SQL)
        self.assertIn("MAX_BY(UNEMPLOYMENT_RATE", MONTHLY_DATA_SQL)
        self.assertIn("MAX_BY(MORTGAGE_RATE_30Y", MONTHLY_DATA_SQL)
        self.assertIn("LIMIT 24", MONTHLY_DATA_SQL)


if __name__ == "__main__":
    unittest.main()
