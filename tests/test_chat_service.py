import unittest
from unittest.mock import Mock, patch

from src.config.app_config import AppSettings
from src.services.chat_service import ChatOutcome, ChatService, ConversationState
from src.services.snowflake_service import ReservationResult, ReservationStatus


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
        self.reserve_patch = patch(
            "src.services.chat_service.reserve_daily_allowance"
        )
        self.complete_patch = patch("src.services.chat_service.complete_answer")
        self.reserve_mock = self.reserve_patch.start()
        self.complete_mock = self.complete_patch.start()
        self.reserve_mock.return_value = ReservationResult(ReservationStatus.RESERVED)
        self.complete_mock.return_value = "Answer"

    def tearDown(self):
        self.reserve_patch.stop()
        self.complete_patch.stop()

    def service(self):
        semaphore = FakeSemaphore()
        return ChatService(self.settings, semaphore), semaphore

    def test_rejected_question_consumes_nothing(self):
        service, semaphore = self.service()
        state = ConversationState()
        session_factory = Mock(return_value=object())

        result = service.submit(session_factory, "csv", state, "Write a poem")

        self.assertEqual(result.outcome, ChatOutcome.UNSUPPORTED_TOPIC)
        self.assertEqual(result.state.chargeable_requests, 0)
        session_factory.assert_not_called()
        self.reserve_mock.assert_not_called()
        self.assertEqual(semaphore.releases, 0)

    def test_immediate_duplicate_reuses_existing_answer(self):
        service, _ = self.service()
        state = ConversationState().with_answer("What is CPI?", "CPI is 320.")
        session_factory = Mock(return_value=object())

        result = service.submit(session_factory, "csv", state, " what  is cpi? ")

        self.assertEqual(result.outcome, ChatOutcome.DUPLICATE)
        self.assertEqual(result.message, "CPI is 320.")
        session_factory.assert_not_called()
        self.reserve_mock.assert_not_called()

    def test_session_limit_blocks_before_snowflake(self):
        service, _ = self.service()
        state = ConversationState(chargeable_requests=5)
        session_factory = Mock(return_value=object())

        result = service.submit(session_factory, "csv", state, "What is CPI?")

        self.assertEqual(result.outcome, ChatOutcome.SESSION_LIMIT)
        session_factory.assert_not_called()
        self.reserve_mock.assert_not_called()

    def test_remembered_daily_limit_blocks_before_opening_session(self):
        service, _ = self.service()
        state = ConversationState(daily_limit_reached=True)
        session_factory = Mock(return_value=object())

        result = service.submit(session_factory, "csv", state, "What is CPI?")

        self.assertEqual(result.outcome, ChatOutcome.DAILY_LIMIT)
        session_factory.assert_not_called()
        self.reserve_mock.assert_not_called()

    def test_busy_request_does_not_reserve_quota(self):
        service, semaphore = self.service()
        semaphore.available = False
        session_factory = Mock(return_value=object())

        result = service.submit(
            session_factory, "csv", ConversationState(), "What is CPI?"
        )

        self.assertEqual(result.outcome, ChatOutcome.BUSY)
        session_factory.assert_not_called()
        self.reserve_mock.assert_not_called()

    def test_daily_limit_is_remembered_without_session_charge(self):
        service, semaphore = self.service()
        self.reserve_mock.return_value = ReservationResult(
            ReservationStatus.DAILY_LIMIT
        )
        session = object()
        session_factory = Mock(return_value=session)

        result = service.submit(
            session_factory, "csv", ConversationState(), "What is CPI?"
        )

        self.assertEqual(result.outcome, ChatOutcome.DAILY_LIMIT)
        self.assertTrue(result.state.daily_limit_reached)
        self.assertEqual(result.state.chargeable_requests, 0)
        self.assertEqual(semaphore.releases, 1)
        session_factory.assert_called_once_with()

    def test_cortex_failure_consumes_quota_but_not_context(self):
        service, semaphore = self.service()
        self.complete_mock.side_effect = RuntimeError("failure")
        session = object()
        session_factory = Mock(return_value=session)

        result = service.submit(
            session_factory, "csv", ConversationState(), "What is CPI?"
        )

        self.assertEqual(result.outcome, ChatOutcome.CORTEX_ERROR)
        self.assertEqual(result.state.chargeable_requests, 1)
        self.assertIsNone(result.state.last_exchange)
        self.assertEqual(semaphore.releases, 1)
        session_factory.assert_called_once_with()

    def test_success_records_answer_and_context(self):
        service, semaphore = self.service()
        self.complete_mock.return_value = "CPI is 320."
        session = object()
        session_factory = Mock(return_value=session)

        result = service.submit(
            session_factory, "csv", ConversationState(), "What is CPI?"
        )

        self.assertEqual(result.outcome, ChatOutcome.ANSWERED)
        self.assertEqual(result.state.chargeable_requests, 1)
        self.assertEqual(result.state.last_exchange.answer, "CPI is 320.")
        self.assertEqual(len(result.state.messages), 2)
        self.assertEqual(semaphore.releases, 1)
        session_factory.assert_called_once_with()
        self.reserve_mock.assert_called_once()
        self.assertEqual(self.reserve_mock.call_args.args[0], session)
        self.assertEqual(self.reserve_mock.call_args.args[1], self.settings)
        self.complete_mock.assert_called_once()
        self.assertEqual(self.complete_mock.call_args.args[0], session)
        self.assertEqual(self.complete_mock.call_args.args[1], self.settings)


if __name__ == "__main__":
    unittest.main()
