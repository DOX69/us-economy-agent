from collections.abc import Callable
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.services.chat_service import ChatOutcome, ChatResult


alt.data_transformers.enable("default", consolidate_datasets=False)


ANALYSING_MESSAGE = "Looking up the latest data..."
METRIC_SKELETON_HEIGHT = 190
SUGGESTION_QUESTIONS = {
    "Highest unemployment month": "When was the highest unemployment rate?",
    "Recent inflation trend": "How has CPI changed over the last few months?",
    "Mortgage rate: January vs. now": (
        "What is the 30-year mortgage rate at the beginning of the year vs. now?"
    ),
}
SUGGESTION_ICONS = (
    ":material/trending_up:",
    ":material/payments:",
    ":material/home:",
)

RESPONSIVE_UI_STYLES = """
.stApp, html, body {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

.st-key-app-shell {
  max-width: 1200px;
  margin-inline: auto;
}

h1, h2, h3, h4, h5, h6, [data-testid="stHeading"] {
  text-wrap: balance;
}

[data-testid="stMetricValue"] {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}

.st-key-suggestion-actions button,
.st-key-chat-composer button {
  min-height: 48px;
  transition: transform 120ms cubic-bezier(0.2, 0, 0, 1), opacity 120ms cubic-bezier(0.2, 0, 0, 1);
}

.st-key-suggestion-actions button:active,
.st-key-chat-composer button:active {
  transform: scale(0.96);
}

.st-key-suggestion-actions button p {
  white-space: normal;
  line-height: 1.25;
}

@media (max-width: 640px) {
  .st-key-app-shell {
    width: 100%;
  }

  .st-key-indicator-grid,
  .st-key-suggestion-actions {
    flex-direction: column;
  }

  .st-key-indicator-grid > [data-testid="stLayoutWrapper"],
  .st-key-suggestion-actions > [data-testid="stElementContainer"] {
    width: 100%;
  }

  .st-key-indicator-grid [data-testid="stMetric"] > div {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 0.75rem;
    align-items: center;
  }

  .st-key-indicator-grid [data-testid="stMetricLabel"] {
    grid-column: 1;
    grid-row: 1;
  }

  .st-key-indicator-grid [data-testid="stMetricValue"] {
    grid-column: 2;
    grid-row: 1;
  }

  .st-key-indicator-grid [data-testid="stMetricValue"] + div {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .st-key-indicator-grid [data-testid="stVegaLiteChart"] {
    display: none;
  }

  .st-key-indicator-grid [data-testid="stCaptionContainer"] {
    display: none;
  }

  .st-key-indicator-grid [data-testid="stElementContainer"]:has([data-testid="stVegaLiteChart"]) {
    display: none;
  }

  .st-key-indicator-grid [data-testid="stVerticalBlockBorderWrapper"] {
    padding-block: 0.25rem;
  }

  .st-key-suggestion-actions button {
    width: 100%;
  }

  .st-key-chat-composer {
    position: sticky;
    bottom: 0.5rem;
    z-index: 10;
    padding-top: 0.5rem;
    background: #0F172A;
  }
}

@media (prefers-reduced-motion: reduce) {
  .st-key-suggestion-actions button,
  .st-key-chat-composer button {
    transition: none;
  }

  .st-key-suggestion-actions button:active,
  .st-key-chat-composer button:active {
    transform: none;
  }
}
"""


def inject_responsive_styles():
    st.html(f"<style>{RESPONSIVE_UI_STYLES}</style>")


def format_percentage_point_delta(value: float, *, decimals: int) -> str:
    return f"{value * 100:+.{decimals}f} pp"


def format_index_point_delta(value: float) -> str:
    return f"{value:+.1f} pts"


def latest_snapshot_caption(data) -> str:
    if "MONTH" not in data.columns:
        return "Latest snapshot unavailable"
    latest = pd.to_datetime(data["MONTH"], errors="coerce").max()
    if pd.isna(latest):
        return "Latest snapshot unavailable"
    return f"Latest snapshot · {latest:%B %Y}"


def session_allowance_caption(remaining: int) -> str:
    if remaining <= 0:
        return "No questions left in this session"
    noun = "question" if remaining == 1 else "questions"
    return f"{remaining} {noun} left in this session"


def prepare_monthly_data(data):
    columns = ["MONTH", "UNEMPLOYMENT_RATE", "CPI", "MORTGAGE_RATE_30Y"]
    prepared = data.loc[:, columns].head(24).copy()
    prepared["MONTH"] = pd.to_datetime(prepared["MONTH"], errors="coerce")
    return prepared.rename(
        columns={
            "MONTH": "Month",
            "UNEMPLOYMENT_RATE": "Unemployment",
            "CPI": "Consumer prices (CPI)",
            "MORTGAGE_RATE_30Y": "30-year mortgage",
        }
    )


def create_metric_placeholders():
    row = st.container(horizontal=True, key="indicator-grid", gap="small")
    return tuple(
        row.skeleton(height=METRIC_SKELETON_HEIGHT, width="stretch")
        for _ in range(3)
    )


def create_workspace_columns():
    return st.columns(
        [1, 1],
        gap="large",
        vertical_alignment="top",
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


def show_latest_metric(
    container,
    data,
    column,
    label,
    formatter,
    *,
    delta_formatter=None,
    help_text=None,
):
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
            
    color_hex = "#60A5FA"
        
    # Construct trend chart data with date index if MONTH column is available
    chart = None
    if "MONTH" in available.columns:
        sub_data = available.iloc[:12][::-1].copy()
        dates = pd.to_datetime(sub_data["MONTH"], errors="coerce")
        values = pd.to_numeric(sub_data[column], errors="coerce").astype(float)
        is_percentage = any(kw in column.lower() for kw in ["rate", "unemployment", "mortgage"])
        chart_df = pd.DataFrame(
            {
                "Date": dates.dt.strftime("%B %Y"),
                "Value": values,
            }
        ).dropna()

        if not chart_df.empty:
            chart_values = chart_df.to_dict(orient="records")
            x_tooltip = alt.Tooltip("Date:O", title="Month")
            if is_percentage:
                y_tooltip = alt.Tooltip("Value:Q", title=label, format=".2%")
            else:
                y_tooltip = alt.Tooltip("Value:Q", title=label, format=",.1f")

            chart = alt.Chart(alt.InlineData(values=chart_values)).mark_line(
                color=color_hex,
                strokeWidth=2,
                interpolate="monotone",
            ).encode(
                x=alt.X("Date:O", axis=None),
                y=alt.Y("Value:Q", axis=None, scale=alt.Scale(zero=False)),
                tooltip=[x_tooltip, y_tooltip],
            ).properties(
                height=40,
                width="container",
            ).configure_view(strokeWidth=0)
            chart.usermeta = {"embedOptions": {"actions": False}}

    # Replace the skeleton placeholder with a bordered container holding both metric and altair_chart
    card = container.container(
        border=True,
        key=f"metric-{column.lower().replace('_', '-')}",
    )
    formatted_delta = None
    if delta_val is not None:
        formatted_delta = (
            delta_formatter(delta_val)
            if delta_formatter is not None
            else formatter(delta_val)
        )
    card.metric(
        label,
        formatter(latest),
        delta=formatted_delta,
        delta_color="blue",
        delta_description=(
            "last month"
            if delta_description is not None
            else None
        ),
        help=help_text,
        border=False,
    )
    if chart is not None:
        card.caption("12-month trend")
        card.altair_chart(chart, width="stretch")


def render_suggestion_buttons():
    with st.container(horizontal=True, key="suggestion-actions", gap="xsmall"):
        for index, (label, question) in enumerate(SUGGESTION_QUESTIONS.items()):
            if st.button(
                label,
                icon=SUGGESTION_ICONS[index],
                key=f"suggestion-{index}",
                width="stretch",
            ):
                return question
    return None




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
