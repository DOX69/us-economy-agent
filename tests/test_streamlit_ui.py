import unittest
from unittest.mock import patch

import pandas as pd

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

    def empty(self):
        self.empty_calls += 1

    def metric(self, label, value):
        self.metrics.append((label, value))


class RecordingStreamlit:
    def __init__(self):
        self.events = []

    def columns(self, count):
        self.events.append(("columns", count))
        return [RecordingColumn(self.events, index) for index in range(count)]

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
        self.assertEqual([event[1] for event in skeleton_events], [0, 1, 2])
        self.assertTrue(all(event[2] > 0 for event in skeleton_events))

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
                "Ask in English about unemployment, CPI/inflation, "
                "or 30-year mortgage rates."
            ],
        )

    def test_does_not_render_warning_for_answer(self):
        assistant = RecordingContext([], "assistant")
        result = ChatResult(ChatOutcome.ANSWERED, ConversationState())

        show_outcome(result, 1_000, assistant)

        self.assertEqual(assistant.warnings, [])


if __name__ == "__main__":
    unittest.main()
