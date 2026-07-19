from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Callable, Any

from src.config.app_config import AppSettings
from src.guardrails.chat_guardrails import Exchange, build_prompt, is_duplicate_question, validate_question
from src.services.snowflake_service import (
    ReservationResult,
    ReservationStatus,
    complete_answer,
    reserve_daily_allowance,
)

if TYPE_CHECKING:
    from snowflake.snowpark import Session


class ChatOutcome(Enum):
    ANSWERED = "answered"
    TOO_LONG = "too_long"
    UNSUPPORTED_TOPIC = "unsupported_topic"
    DUPLICATE = "duplicate"
    SESSION_LIMIT = "session_limit"
    BUSY = "busy"
    DAILY_LIMIT = "daily_limit"
    PROMPT_TOO_LARGE = "prompt_too_large"
    UNAVAILABLE = "unavailable"
    CORTEX_ERROR = "cortex_error"


@dataclass(frozen=True)
class ConversationState:
    messages: tuple[dict[str, str], ...] = field(default_factory=tuple)
    chargeable_requests: int = 0
    last_exchange: Exchange | None = None
    daily_limit_reached: bool = False

    def with_answer(self, question: str, answer: str) -> "ConversationState":
        messages = self.messages + (
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        )
        return replace(
            self, messages=messages, last_exchange=Exchange(question, answer)
        )

    def with_error(self, question: str, message: str) -> "ConversationState":
        messages = self.messages + (
            {"role": "user", "content": question},
            {"role": "assistant", "content": message},
        )
        return replace(self, messages=messages)


@dataclass(frozen=True)
class ChatResult:
    outcome: ChatOutcome
    state: ConversationState
    message: str = ""
    error: Exception | None = None


class ChatService:
    def __init__(self, settings: AppSettings, semaphore):
        self.settings = settings
        self.semaphore = semaphore

    def submit(
        self,
        session_factory: Callable[[], "Session"],
        data: Any,
        state: ConversationState,
        question: str,
    ) -> ChatResult:
        validation = validate_question(
            question,
            self.settings.max_question_chars,
            state.last_exchange is not None,
        )
        if not validation.is_valid:
            outcome = (
                ChatOutcome.TOO_LONG
                if validation.reason == "too_long"
                else ChatOutcome.UNSUPPORTED_TOPIC
            )
            return ChatResult(outcome, state)

        if state.last_exchange and is_duplicate_question(
            question, state.last_exchange.question
        ):
            return ChatResult(ChatOutcome.DUPLICATE, state, state.last_exchange.answer)
        if state.daily_limit_reached:
            return ChatResult(ChatOutcome.DAILY_LIMIT, state)
        if state.chargeable_requests >= self.settings.session_allowance:
            return ChatResult(ChatOutcome.SESSION_LIMIT, state)
        if not self.semaphore.acquire(blocking=False):
            return ChatResult(ChatOutcome.BUSY, state)

        try:
            prompt = build_prompt(data, question, state.last_exchange)
            session = session_factory()
            reservation = reserve_daily_allowance(session, self.settings, prompt)
            if reservation.status != ReservationStatus.RESERVED:
                return self._reservation_failure(state, reservation)

            charged = replace(
                state, chargeable_requests=state.chargeable_requests + 1
            )
            try:
                answer = complete_answer(session, self.settings, prompt)
            except Exception as error:
                message = "The AI service is temporarily unavailable."
                return ChatResult(
                    ChatOutcome.CORTEX_ERROR,
                    charged.with_error(question, message),
                    message,
                    error,
                )
            return ChatResult(
                ChatOutcome.ANSWERED,
                charged.with_answer(question, answer),
                answer,
            )
        finally:
            self.semaphore.release()

    @staticmethod
    def _reservation_failure(
        state: ConversationState, reservation: ReservationResult
    ) -> ChatResult:
        outcomes = {
            ReservationStatus.DAILY_LIMIT: ChatOutcome.DAILY_LIMIT,
            ReservationStatus.PROMPT_TOO_LARGE: ChatOutcome.PROMPT_TOO_LARGE,
            ReservationStatus.UNAVAILABLE: ChatOutcome.UNAVAILABLE,
        }
        if reservation.status == ReservationStatus.DAILY_LIMIT:
            state = replace(state, daily_limit_reached=True)
        return ChatResult(
            outcomes[reservation.status], state, error=reservation.error
        )
