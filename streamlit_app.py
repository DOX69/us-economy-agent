import logging
import threading

import streamlit as st

from src.config.app_config import ConfigError, load_settings
from src.services.chat_service import ChatOutcome, ChatService, ConversationState
from src.services.snowflake_service import (
    MONTHLY_DATA_SQL,
    complete_answer,
    reserve_daily_allowance,
)


LOGGER = logging.getLogger(__name__)


@st.cache_resource
def get_request_semaphore(max_concurrent_requests: int):
    return threading.BoundedSemaphore(max_concurrent_requests)


def show_latest_metric(container, data, column, label, formatter):
    available = data.dropna(subset=[column])
    if not available.empty:
        container.metric(label, formatter(available.iloc[0][column]))


def show_outcome(result, max_question_chars):
    messages = {
        ChatOutcome.TOO_LONG: (
            f"Keep your question under {max_question_chars:,} characters."
        ),
        ChatOutcome.UNSUPPORTED_TOPIC: (
            "Ask in English about unemployment, CPI/inflation, or 30-year mortgage rates."
        ),
        ChatOutcome.DUPLICATE: "This question was already answered above.",
        ChatOutcome.SESSION_LIMIT: "You have used all questions for this session.",
        ChatOutcome.BUSY: "The public demo is busy. Please try again shortly.",
        ChatOutcome.DAILY_LIMIT: (
            "The public demo has reached today's AI allowance. Try again after 00:00 UTC."
        ),
        ChatOutcome.PROMPT_TOO_LARGE: (
            "This follow-up needs too much context. Ask it as a standalone question."
        ),
        ChatOutcome.UNAVAILABLE: "The AI service is temporarily unavailable.",
    }
    if result.outcome in messages:
        st.warning(messages[result.outcome])


st.set_page_config(page_title="Ask the US Economy", page_icon="📊")

try:
    settings = load_settings(st.secrets)
except (ConfigError, FileNotFoundError):
    st.error("Application configuration is incomplete.")
    st.stop()

try:
    connection = st.connection(
        "snowflake", ttl=settings.app.connection_ttl_seconds
    )
    data = connection.query(
        MONTHLY_DATA_SQL,
        ttl=settings.app.data_cache_ttl_seconds,
        show_spinner=False,
    )
except Exception:
    LOGGER.exception("monthly_data_load_failed")
    st.error("Economic data is temporarily unavailable.")
    st.stop()

st.title("📊 Ask the US Economy")
st.caption("Powered by Snowflake Cortex • Data: BLS & Freddie Mac")

column_one, column_two, column_three = st.columns(3)
show_latest_metric(
    column_one,
    data,
    "UNEMPLOYMENT_RATE",
    "Unemployment",
    lambda value: f"{value * 100:.1f}%",
)
show_latest_metric(
    column_two, data, "CPI", "CPI Index", lambda value: f"{value:.1f}"
)
show_latest_metric(
    column_three,
    data,
    "MORTGAGE_RATE_30Y",
    "30Y Mortgage",
    lambda value: f"{value * 100:.2f}%",
)

st.divider()

if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = ConversationState()
state = st.session_state.conversation_state

for message in state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

st.caption(
    f"Questions used: {state.chargeable_requests}/{settings.app.session_allowance}"
)
is_chat_disabled = (
    state.daily_limit_reached
    or state.chargeable_requests >= settings.app.session_allowance
)

question = st.chat_input(
    "Ask about unemployment, inflation, or mortgage rates...",
    disabled=is_chat_disabled,
    max_chars=settings.app.max_question_chars,
)
if question:
    data_csv = (
        data.sort_values("MONTH", ascending=False)
        .to_csv(index=False, date_format="%Y-%m", na_rep="")
        .strip()
    )
    service = ChatService(
        settings.app,
        get_request_semaphore(settings.app.max_concurrent_requests),
        reserve_daily_allowance,
        complete_answer,
    )
    result = service.submit(connection.session, data_csv, state, question)
    st.session_state.conversation_state = result.state

    if result.error:
        error_info = (
            type(result.error),
            result.error,
            result.error.__traceback__,
        )
        LOGGER.error(
            "chat_request_failed outcome=%s error_type=%s",
            result.outcome.value,
            type(result.error).__name__,
            exc_info=error_info,
        )
    if result.outcome in (ChatOutcome.ANSWERED, ChatOutcome.CORTEX_ERROR):
        st.rerun()
    show_outcome(result, settings.app.max_question_chars)

with st.expander("📋 View monthly data"):
    st.dataframe(data, use_container_width=True)
