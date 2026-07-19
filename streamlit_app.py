import logging
import threading

import streamlit as st

from src.config.app_config import ConfigError, load_settings
from src.services.chat_service import ChatOutcome, ConversationState, handle_chat_request
from src.services.snowflake_service import MONTHLY_DATA_SQL
from src.streamlit_ui import (
    clear_metric_placeholders,
    create_metric_placeholders,
    get_chat_question,
    run_visible_chat_request,
    show_latest_metric,
    show_outcome,
)


LOGGER = logging.getLogger(__name__)


@st.cache_resource
def get_request_semaphore(max_concurrent_requests: int):
    return threading.BoundedSemaphore(max_concurrent_requests)


st.set_page_config(page_title="Ask the US Economy", page_icon="📊")

try:
    settings = load_settings(st.secrets)
except (ConfigError, FileNotFoundError):
    st.error("Application configuration is incomplete.")
    st.stop()

st.title("📊 Ask the US Economy")
st.caption("Powered by Snowflake Cortex • Data: BLS & Freddie Mac")
metric_placeholders = create_metric_placeholders()

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
    clear_metric_placeholders(metric_placeholders)
    st.error("Economic data is temporarily unavailable.")
    st.stop()

show_latest_metric(
    metric_placeholders[0],
    data,
    "UNEMPLOYMENT_RATE",
    "Unemployment",
    lambda value: f"{value * 100:.1f}%",
)
show_latest_metric(
    metric_placeholders[1], data, "CPI", "CPI Index", lambda value: f"{value:.1f}"
)
show_latest_metric(
    metric_placeholders[2],
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

question = get_chat_question(
    "Ask about unemployment, inflation, or mortgage rates...",
    is_chat_disabled,
    settings.app.max_question_chars,
)
if question:
    result, assistant_message = run_visible_chat_request(
        question,
        lambda: handle_chat_request(
            connection.session,
            data,
            state,
            question,
            settings.app,
            get_request_semaphore(settings.app.max_concurrent_requests),
        ),
    )
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
    show_outcome(result, settings.app.max_question_chars, assistant_message)

with st.expander("📋 View monthly data"):
    st.dataframe(data, width="stretch")
