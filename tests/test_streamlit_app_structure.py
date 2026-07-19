from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "streamlit_app.py"


def test_app_wires_the_responsive_ui_contract():
    source = APP_SOURCE.read_text(encoding="utf-8")
    expected_snippets = (
        'layout="wide"',
        "inject_responsive_styles()",
        "overview_column, chat_column = create_workspace_columns()",
        "with overview_column:",
        "with chat_column:",
        "render_suggestion_buttons()",
        "latest_snapshot_caption(data)",
        "session_allowance_caption(remaining)",
        'st.expander("Explore 24 months of data"',
        "prepare_monthly_data(data)",
        '"CPI (prices)"',
    )

    missing = [snippet for snippet in expected_snippets if snippet not in source]
    assert not missing, f"Missing responsive UI wiring: {missing}"
