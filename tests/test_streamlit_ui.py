import unittest
from decimal import Decimal
from unittest.mock import patch

import pandas as pd

import src.streamlit_ui as streamlit_ui
from src.services.chat_service import ChatOutcome, ChatResult, ConversationState
from src.streamlit_ui import (
    ANALYSING_MESSAGE,
    clear_metric_placeholders,
    create_metric_placeholders,
    get_chat_question,
    run_visible_chat_request,
    show_latest_metric,
    show_outcome,
)


class RecordingContext:
    def __init__(self, events, name):
        self.events = events
        self.name = name
        self.warnings = []

    def __enter__(self):
        self.events.append(("enter", self.name))
        return self

    def __exit__(self, *_):
        self.events.append(("exit", self.name))

    def warning(self, message):
        self.warnings.append(message)


class RecordingColumn:
    def __init__(self, events, index):
        self.events = events
        self.index = index

    def skeleton(self, *, height):
        placeholder = object()
        self.events.append(("skeleton", self.index, height, placeholder))
        return placeholder


class RecordingPlaceholder:
    def __init__(self):
        self.empty_calls = 0
        self.metrics = []
        self.metric_kwargs = {}
        self.altair_charts = []
        self.captions = []

    def empty(self):
        self.empty_calls += 1

    def container(self, border=False, **kwargs):
        return self

    def metric(self, label, value, **kwargs):
        self.metrics.append((label, value))
        self.metric_kwargs = kwargs

    def altair_chart(self, chart, **kwargs):
        self.altair_charts.append(chart)

    def caption(self, message):
        self.captions.append(message)



class RecordingStreamlit:
    def __init__(self):
        self.events = []

    def columns(self, count, **kwargs):
        self.events.append(("columns", count, kwargs))
        return [RecordingColumn(self.events, index) for index in range(len(count))]

    def container(self, **kwargs):
        self.events.append(("container", kwargs))
        return self

    def skeleton(self, *, height, width="stretch"):
        placeholder = object()
        self.events.append(("skeleton", height, width, placeholder))
        return placeholder

    def chat_message(self, role):
        self.events.append(("chat_message", role))
        return RecordingContext(self.events, role)

    def markdown(self, content):
        self.events.append(("markdown", content))

    def spinner(self, message):
        self.events.append(("spinner", message))
        return RecordingContext(self.events, "spinner")

    def chat_input(self, placeholder, **kwargs):
        self.events.append(("chat_input", placeholder, kwargs))
        return "submitted question"


class StreamlitUiTests(unittest.TestCase):
    def test_creates_three_metric_skeletons(self):
        fake_st = RecordingStreamlit()

        with patch("src.streamlit_ui.st", fake_st):
            placeholders = create_metric_placeholders()

        skeleton_events = [event for event in fake_st.events if event[0] == "skeleton"]
        self.assertEqual(len(placeholders), 3)
        self.assertEqual(len(skeleton_events), 3)
        self.assertIn(
            (
                "container",
                {
                    "horizontal": True,
                    "key": "indicator-grid",
                    "gap": "small",
                },
            ),
            fake_st.events,
        )

    def test_clears_all_metric_placeholders(self):
        placeholders = [RecordingPlaceholder() for _ in range(3)]

        clear_metric_placeholders(placeholders)

        self.assertEqual([item.empty_calls for item in placeholders], [1, 1, 1])

    def test_disables_chat_input_during_submission(self):
        fake_st = RecordingStreamlit()

        with patch("src.streamlit_ui.st", fake_st):
            question = get_chat_question("Ask a question", False, 1_000)

        self.assertEqual(question, "submitted question")
        self.assertEqual(
            fake_st.events,
            [
                (
                    "chat_input",
                    "Ask a question",
                    {
                        "disabled": False,
                        "max_chars": 1_000,
                        "submit_mode": "disable",
                    },
                )
            ],
        )

    def test_replaces_metric_skeleton_with_latest_value(self):
        placeholder = RecordingPlaceholder()
        data = pd.DataFrame({"CPI": [321.5, 320.0]})

        show_latest_metric(
            placeholder,
            data,
            "CPI",
            "CPI Index",
            lambda value: f"{value:.1f}",
        )

        self.assertEqual(placeholder.metrics, [("CPI Index", "321.5")])
        self.assertEqual(placeholder.empty_calls, 0)

    def test_metric_uses_neutral_color_and_explicit_percentage_point_delta(self):
        formatter = getattr(streamlit_ui, "format_percentage_point_delta", None)
        self.assertTrue(callable(formatter))
        placeholder = RecordingPlaceholder()
        data = pd.DataFrame(
            {
                "UNEMPLOYMENT_RATE": [0.039, 0.040],
                "MONTH": pd.to_datetime(["2026-06-01", "2026-05-01"]),
            }
        )

        show_latest_metric(
            placeholder,
            data,
            "UNEMPLOYMENT_RATE",
            "Unemployment",
            lambda value: f"{value * 100:.1f}%",
            delta_formatter=lambda value: formatter(value, decimals=1),
        )

        self.assertEqual(placeholder.metric_kwargs["delta"], "-0.1 pp")
        self.assertEqual(placeholder.metric_kwargs["delta_color"], "blue")
        self.assertEqual(
            placeholder.metric_kwargs["delta_description"],
            "last month",
        )
        self.assertEqual(placeholder.captions, ["12-month trend"])
        self.assertNotIn(
            "title",
            placeholder.altair_charts[0].to_dict(),
        )
        self.assertEqual(
            placeholder.altair_charts[0].to_dict()["mark"],
            {
                "type": "line",
                "color": "#60A5FA",
                "interpolate": "monotone",
                "strokeWidth": 2,
            },
        )

    def test_metric_normalizes_snowflake_values_for_chart_rendering(self):
        placeholder = RecordingPlaceholder()
        data = pd.DataFrame(
            {
                "CPI": [Decimal("330.3"), Decimal("327.5")],
                "MONTH": ["2026-06-01", "2026-05-01"],
            }
        )

        show_latest_metric(
            placeholder,
            data,
            "CPI",
            "CPI (prices)",
            lambda value: f"{value:.1f}",
        )

        chart_spec = placeholder.altair_charts[0].to_dict()
        self.assertEqual(
            chart_spec["data"]["values"],
            [
                {"Date": "May 2026", "Value": 327.5},
                {"Date": "June 2026", "Value": 330.3},
            ],
        )
        self.assertNotIn("datasets", chart_spec)

    def test_clears_metric_skeleton_when_value_is_unavailable(self):
        placeholder = RecordingPlaceholder()
        data = pd.DataFrame({"CPI": [None]})

        show_latest_metric(placeholder, data, "CPI", "CPI Index", str)

        self.assertEqual(placeholder.metrics, [])
        self.assertEqual(placeholder.empty_calls, 1)

    def test_renders_question_and_spinner_before_request(self):
        fake_st = RecordingStreamlit()
        expected_result = object()

        def request():
            fake_st.events.append(("request",))
            return expected_result

        with patch("src.streamlit_ui.st", fake_st):
            result, assistant = run_visible_chat_request("What is CPI?", request)

        self.assertIs(result, expected_result)
        self.assertEqual(
            fake_st.events,
            [
                ("chat_message", "user"),
                ("enter", "user"),
                ("markdown", "What is CPI?"),
                ("exit", "user"),
                ("chat_message", "assistant"),
                ("enter", "assistant"),
                ("spinner", ANALYSING_MESSAGE),
                ("enter", "spinner"),
                ("request",),
                ("exit", "spinner"),
                ("exit", "assistant"),
            ],
        )
        self.assertEqual(assistant.name, "assistant")

    def test_renders_rejected_outcome_in_assistant_message(self):
        assistant = RecordingContext([], "assistant")
        result = ChatResult(ChatOutcome.UNSUPPORTED_TOPIC, ConversationState())

        show_outcome(result, 1_000, assistant)

        self.assertEqual(
            assistant.warnings,
            [
                "I can only answer questions about unemployment,"
                " inflation (CPI), or 30-year mortgage rates, in English."
            ],
        )

    def test_does_not_render_warning_for_answer(self):
        assistant = RecordingContext([], "assistant")
        result = ChatResult(ChatOutcome.ANSWERED, ConversationState())

        show_outcome(result, 1_000, assistant)

        self.assertEqual(assistant.warnings, [])

    def test_formats_index_point_delta_with_explicit_sign_and_unit(self):
        formatter = getattr(streamlit_ui, "format_index_point_delta", None)
        self.assertTrue(callable(formatter))
        self.assertEqual(formatter(2.8), "+2.8 pts")
        self.assertEqual(formatter(-1.2), "-1.2 pts")

    def test_formats_latest_snapshot_caption(self):
        formatter = getattr(streamlit_ui, "latest_snapshot_caption", None)
        self.assertTrue(callable(formatter))
        data = pd.DataFrame(
            {"MONTH": pd.to_datetime(["2026-05-01", "2026-06-01"])}
        )

        self.assertEqual(formatter(data), "Latest snapshot · June 2026")

    def test_formats_session_allowance_as_contextual_composer_copy(self):
        formatter = getattr(streamlit_ui, "session_allowance_caption", None)
        self.assertTrue(callable(formatter))
        self.assertEqual(formatter(5), "5 questions left in this session")
        self.assertEqual(formatter(1), "1 question left in this session")
        self.assertEqual(formatter(0), "No questions left in this session")

    def test_uses_short_suggestion_labels_that_fit_mobile(self):
        suggestions = getattr(streamlit_ui, "SUGGESTION_QUESTIONS", None)
        self.assertIsNotNone(suggestions)
        self.assertEqual(
            list(suggestions),
            [
                "Highest unemployment month",
                "Recent inflation trend",
                "Mortgage rate: January vs. now",
            ],
        )
        self.assertTrue(all(len(label) <= 33 for label in suggestions))

    def test_prepares_readable_monthly_data(self):
        prepare = getattr(streamlit_ui, "prepare_monthly_data", None)
        self.assertTrue(callable(prepare))
        data = pd.DataFrame(
            {
                "MONTH": pd.to_datetime(["2026-06-01"]),
                "UNEMPLOYMENT_RATE": [0.039],
                "CPI": [330.3],
                "MORTGAGE_RATE_30Y": [0.063],
                "INTERNAL": ["hidden"],
            }
        )

        result = prepare(data)

        self.assertEqual(
            list(result.columns),
            ["Month", "Unemployment", "Consumer prices (CPI)", "30-year mortgage"],
        )
        self.assertEqual(result.iloc[0]["Unemployment"], 0.039)
        self.assertNotIn("INTERNAL", result.columns)

    def test_responsive_styles_cover_touch_targets_and_reduced_motion(self):
        styles = getattr(streamlit_ui, "RESPONSIVE_UI_STYLES", None)
        self.assertIsInstance(styles, str)
        self.assertIn("@media (max-width: 640px)", styles)
        self.assertIn("min-height: 48px", styles)
        self.assertIn(
            ".st-key-indicator-grid,\n  .st-key-suggestion-actions {\n    flex-direction: column;",
            styles,
        )
        self.assertIn(
            '[data-testid="stElementContainer"]:has([data-testid="stVegaLiteChart"])',
            styles,
        )
        self.assertIn("prefers-reduced-motion: reduce", styles)
        self.assertIn(".st-key-chat-composer", styles)
        self.assertNotIn("box-shadow", styles)

    def test_creates_balanced_desktop_workspace_columns(self):
        create_columns = getattr(streamlit_ui, "create_workspace_columns", None)
        self.assertTrue(callable(create_columns))
        fake_st = RecordingStreamlit()

        with patch("src.streamlit_ui.st", fake_st):
            columns = create_columns()

        self.assertEqual(len(columns), 2)
        self.assertEqual(
            fake_st.events,
            [
                (
                    "columns",
                    [1, 1],
                    {"gap": "large", "vertical_alignment": "top"},
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
