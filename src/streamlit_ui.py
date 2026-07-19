from collections.abc import Callable
from typing import Any

import streamlit as st

from src.services.chat_service import ChatOutcome, ChatResult


ANALYSING_MESSAGE = "Looking up the latest data..."
METRIC_SKELETON_HEIGHT = 150


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


import pandas as pd
import altair as alt

def show_latest_metric(container, data, column, label, formatter):
    available = data.dropna(subset=[column])
    if available.empty:
        container.empty()
        return
    latest = available.iloc[0][column]
    
    # Calculate delta
    delta_val = None
    delta_description = None
    if len(available) >= 2:
        previous = available.iloc[1][column]
        if previous is not None:
            delta_val = latest - previous
            delta_description = "vs. last month"
            
    # Set default delta color logic
    if delta_val is None:
        color_hex = "#60A5FA"  # blue
    elif delta_val < 0:
        color_hex = "#F87171"  # red (standard negative)
    else:
        color_hex = "#34D399"  # green (standard positive)
        
    # Construct trend chart data with date index if MONTH column is available
    chart = None
    if "MONTH" in available.columns:
        sub_data = available.iloc[:12][::-1].copy()
        try:
            if pd.api.types.is_datetime64_any_dtype(sub_data['MONTH']):
                dates = sub_data['MONTH'].dt.strftime('%b %Y')
            else:
                dates = pd.to_datetime(sub_data['MONTH']).dt.strftime('%b %Y')
        except Exception:
            dates = sub_data['MONTH'].astype(str)
            
        values = sub_data[column].copy()
        is_percentage = any(kw in column.lower() for kw in ["rate", "unemployment", "mortgage"])
        
        chart_df = pd.DataFrame({
            "Date": dates.values,
            "Value": values.values
        })
        
        # Build custom Altair sparkline with tooltips
        x_tooltip = alt.Tooltip('Date:O', title='Date')
        if is_percentage:
            y_tooltip = alt.Tooltip('Value:Q', title=label, format='.1%')
        else:
            y_tooltip = alt.Tooltip('Value:Q', title=label, format=',.1f')
            
        chart = alt.Chart(chart_df).mark_area(
            line={'color': color_hex, 'width': 2},
            color=alt.Gradient(
                gradient='linear',
                stops=[
                    alt.GradientStop(color=color_hex, offset=0),
                    alt.GradientStop(color='transparent', offset=1)
                ],
                x1=1, y1=1, x2=1, y2=0
            ),
            opacity=0.2
        ).encode(
            x=alt.X('Date:O', axis=alt.Axis(labels=False, grid=False, ticks=False, title=None, domain=False)),
            y=alt.Y('Value:Q', axis=alt.Axis(labels=False, grid=False, ticks=False, title=None, domain=False), scale=alt.Scale(zero=False)),
            tooltip=[x_tooltip, y_tooltip]
        ).properties(
            height=40,
            width='container'
        ).configure_view(
            strokeWidth=0
        )
        chart.usermeta = {"embedOptions": {"actions": False}}

    # Replace the skeleton placeholder with a bordered container holding both metric and altair_chart
    card = container.container(border=True)
    card.metric(
        label,
        formatter(latest),
        delta=formatter(delta_val) if delta_val is not None else None,
        delta_description=delta_description,
        border=False,
    )
    if chart is not None:
        card.altair_chart(chart, width="stretch")




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
            "That question is too long."
            f" Try rephrasing in under {max_question_chars:,} characters."
        ),
        ChatOutcome.UNSUPPORTED_TOPIC: (
            "I can only answer questions about unemployment,"
            " inflation (CPI), or 30-year mortgage rates, in English."
        ),
        ChatOutcome.DUPLICATE: (
            "You already asked that. Scroll up to see the answer."
        ),
        ChatOutcome.SESSION_LIMIT: (
            "You've reached the limit for this session."
            " Refresh to start a new one."
        ),
        ChatOutcome.BUSY: (
            "Too many people asking at once."
            " Try again in a few seconds."
        ),
        ChatOutcome.DAILY_LIMIT: (
            "Today's AI budget is used up."
            " Come back tomorrow (resets at midnight UTC)."
        ),
        ChatOutcome.PROMPT_TOO_LARGE: (
            "That follow-up is too complex."
            " Try asking it as a standalone question."
        ),
        ChatOutcome.UNAVAILABLE: (
            "The AI service is down right now."
            " Try again in a minute."
        ),
    }
    if result.outcome in messages:
        container.warning(messages[result.outcome])
