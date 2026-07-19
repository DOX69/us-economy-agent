import logging
import threading

import streamlit as st

from src.config.app_config import ConfigError, load_settings
from src.services.chat_service import ChatOutcome, ConversationState, handle_chat_request
from src.services.snowflake_service import MONTHLY_DATA_SQL
from src.streamlit_ui import (
    clear_metric_placeholders,
    create_metric_placeholders,
    create_workspace_columns,
    format_index_point_delta,
    format_percentage_point_delta,
    get_chat_question,
    inject_responsive_styles,
    latest_snapshot_caption,
    prepare_monthly_data,
    render_suggestion_buttons,
    run_visible_chat_request,
    session_allowance_caption,
    show_latest_metric,
    show_outcome,
)


LOGGER = logging.getLogger(__name__)


@st.cache_resource
def get_request_semaphore(max_concurrent_requests: int):
    return threading.BoundedSemaphore(max_concurrent_requests)


st.set_page_config(
    page_title="Ask the US Economy",
    page_icon=":material/query_stats:",
    layout="wide",
)
inject_responsive_styles()

try:
    settings = load_settings(st.secrets)
except (ConfigError, FileNotFoundError):
    st.error(
        "Application configuration is incomplete.",
        icon=":material/error:",
    )
    st.stop()

with st.container(key="app-shell"):
    st.title("Ask the US economy")
    st.caption("Live BLS & Freddie Mac data · Answers by Snowflake Cortex")
    overview_column, chat_column = create_workspace_columns()

    with overview_column:
        st.subheader("Latest indicators")
        snapshot_placeholder = st.empty()
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
    st.error(
        "Economic data is temporarily unavailable.",
        icon=":material/cloud_off:",
    )
    st.stop()

show_latest_metric(
    metric_placeholders[0],
    data,
    "UNEMPLOYMENT_RATE",
    "Unemployment",
    lambda value: f"{value * 100:.1f}%",
    delta_formatter=lambda value: format_percentage_point_delta(
        value,
        decimals=1,
    ),
    help_text="Share of the US labor force that is unemployed.",
)
show_latest_metric(
    metric_placeholders[1],
    data,
    "CPI",
    "CPI (prices)",
    lambda value: f"{value:.1f}",
    delta_formatter=format_index_point_delta,
    help_text="Consumer Price Index for All Urban Consumers.",
)
show_latest_metric(
    metric_placeholders[2],
    data,
    "MORTGAGE_RATE_30Y",
    "30-year mortgage",
    lambda value: f"{value * 100:.2f}%",
    delta_formatter=lambda value: format_percentage_point_delta(
        value,
        decimals=2,
    ),
    help_text="Average US 30-year fixed mortgage rate.",
)
snapshot_placeholder.caption(latest_snapshot_caption(data))

if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = ConversationState()
state = st.session_state.conversation_state

remaining = settings.app.session_allowance - state.chargeable_requests
is_chat_disabled = state.daily_limit_reached or remaining <= 0

with overview_column:
    with st.expander("Explore 24 months of data", icon=":material/table_chart:"):
        st.dataframe(
            prepare_monthly_data(data),
            hide_index=True,
            height=320,
            column_config={
                "Month": st.column_config.DateColumn("Month", format="MMM YYYY"),
                "Unemployment": st.column_config.NumberColumn(
                    "Unemployment",
                    format="percent",
                ),
                "Consumer prices (CPI)": st.column_config.NumberColumn(
                    "Consumer prices (CPI)",
                    format="%.1f",
                ),
                "30-year mortgage": st.column_config.NumberColumn(
                    "30-year mortgage",
                    format="percent",
                ),
            },
        )

with chat_column:
    with st.container(border=True, key="conversation-panel"):
        st.subheader("Ask a question")
        st.caption("Answers use the latest 24 monthly snapshots.")

        selected = None
        if not state.messages:
            st.caption("Try one of these")
            selected = render_suggestion_buttons()

        conversation = st.container(key="conversation")
        with conversation:
            for message in state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        st.caption(f":material/chat: {session_allowance_caption(remaining)}")
        with st.container(key="chat-composer"):
            question = get_chat_question(
                "Ask about unemployment, inflation, or mortgage rates...",
                is_chat_disabled,
                settings.app.max_question_chars,
            )

        if selected and not question:
            question = selected

        if question:
            result, assistant_message = run_visible_chat_request(
                conversation,
                question,
                lambda: handle_chat_request(
                    connection.session,
                    data,
                    state,
                    question,
                    settings.app,
                    get_request_semaphore(
                        settings.app.max_concurrent_requests
                    ),
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
            if result.outcome in (
                ChatOutcome.ANSWERED,
                ChatOutcome.CORTEX_ERROR,
            ):
                st.rerun()
            show_outcome(
                result,
                settings.app.max_question_chars,
                assistant_message,
            )
