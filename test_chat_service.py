import unittest

from app_config import AppSettings
from chat_service import ChatOutcome, ChatService, ConversationState
from snowflake_service import ReservationResult, ReservationStatus


class FakeSemaphore:
    def __init__(self, available=True):
        self.available = available
        self.releases = 0

    def acquire(self, blocking=False):
        self.blocking = blocking
        return self.available

    def release(self):
        self.releases += 1


class ChatServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings()
        self.reserve_calls = 0
        self.complete_calls = 0

    def service(self, reservation=ReservationStatus.RESERVED, answer="Answer"):
        def reserve(_session, _settings, _prompt):
            self.reserve_calls += 1
            return ReservationResult(reservation)

        def complete(_session, _settings, _prompt):
            self.complete_calls += 1
            if isinstance(answer, Exception):
                raise answer
            return answer

        semaphore = FakeSemaphore()
        return ChatService(self.settings, semaphore, reserve, complete), semaphore

    def test_rejected_question_consumes_nothing(self):
        service, semaphore = self.service()
        state = ConversationState()
        session_calls = []

        result = service.submit(
            lambda: session_calls.append("called"), "csv", state, "Write a poem"
        )

        self.assertEqual(result.outcome, ChatOutcome.UNSUPPORTED_TOPIC)
        self.assertEqual(result.state.chargeable_requests, 0)
        self.assertEqual(self.reserve_calls, 0)
        self.assertEqual(semaphore.releases, 0)
        self.assertEqual(session_calls, [])

    def test_immediate_duplicate_reuses_existing_answer(self):
        service, _ = self.service()
        state = ConversationState().with_answer("What is CPI?", "CPI is 320.")

        result = service.submit(None, "csv", state, " what  is cpi? ")

        self.assertEqual(result.outcome, ChatOutcome.DUPLICATE)
        self.assertEqual(result.message, "CPI is 320.")
        self.assertEqual(self.reserve_calls, 0)

    def test_session_limit_blocks_before_snowflake(self):
        service, _ = self.service()
        state = ConversationState(chargeable_requests=5)

        result = service.submit(None, "csv", state, "What is CPI?")

        self.assertEqual(result.outcome, ChatOutcome.SESSION_LIMIT)
        self.assertEqual(self.reserve_calls, 0)

    def test_busy_request_does_not_reserve_quota(self):
        service, semaphore = self.service()
        semaphore.available = False

        result = service.submit(None, "csv", ConversationState(), "What is CPI?")

        self.assertEqual(result.outcome, ChatOutcome.BUSY)
        self.assertEqual(self.reserve_calls, 0)

    def test_daily_limit_is_remembered_without_session_charge(self):
        service, semaphore = self.service(ReservationStatus.DAILY_LIMIT)

        result = service.submit(None, "csv", ConversationState(), "What is CPI?")

        self.assertEqual(result.outcome, ChatOutcome.DAILY_LIMIT)
        self.assertTrue(result.state.daily_limit_reached)
        self.assertEqual(result.state.chargeable_requests, 0)
        self.assertEqual(semaphore.releases, 1)

    def test_cortex_failure_consumes_quota_but_not_context(self):
        service, semaphore = self.service(answer=RuntimeError("failure"))

        result = service.submit(None, "csv", ConversationState(), "What is CPI?")

        self.assertEqual(result.outcome, ChatOutcome.CORTEX_ERROR)
        self.assertEqual(result.state.chargeable_requests, 1)
        self.assertIsNone(result.state.last_exchange)
        self.assertEqual(semaphore.releases, 1)

    def test_success_records_answer_and_context(self):
        service, semaphore = self.service(answer="CPI is 320.")
        session = object()
        session_calls = []

        result = service.submit(
            lambda: session_calls.append("called") or session,
            "csv",
            ConversationState(),
            "What is CPI?",
        )

        self.assertEqual(result.outcome, ChatOutcome.ANSWERED)
        self.assertEqual(result.state.chargeable_requests, 1)
        self.assertEqual(result.state.last_exchange.answer, "CPI is 320.")
        self.assertEqual(len(result.state.messages), 2)
        self.assertEqual(semaphore.releases, 1)
        self.assertEqual(session_calls, ["called"])


if __name__ == "__main__":
    unittest.main()
