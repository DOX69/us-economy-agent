from collections.abc import Callable
from typing import Any

import streamlit as st

from src.services.chat_service import ChatOutcome, ChatResult


ANALYSING_MESSAGE = "Analysing economic data..."
METRIC_SKELETON_HEIGHT = 80


def create_metric_placeholders():
    return tuple(
        column.skeleton(height=METRIC_SKELETON_HEIGHT)
        for column in st.columns(3)
    )


def clear_metric_placeholders(placeholders):
    for placeholder in placeholders:
        placeholder.empty()


def get_chat_question(placeholder: str, disabled: bool, max_chars: int):
    return st.chat_input(
        placeholder,
        disabled=disabled,
        max_chars=max_chars,
        submit_mode="disable",
    )


def show_latest_metric(container, data, column, label, formatter):
    available = data.dropna(subset=[column])
    if available.empty:
        container.empty()
        return
    container.metric(label, formatter(available.iloc[0][column]))


def run_visible_chat_request(question: str, request: Callable[[], Any]):
    with st.chat_message("user"):
        st.markdown(question)

    assistant = st.chat_message("assistant")
    with assistant:
        with st.spinner(ANALYSING_MESSAGE):
            result = request()
    return result, assistant


def show_outcome(result: ChatResult, max_question_chars: int, container):
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
        container.warning(messages[result.outcome])
