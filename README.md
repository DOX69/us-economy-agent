<p align="center">
  <img src="./assets/readme/hero.svg" width="100%"
       alt="US Economy Agent: ask the US economy plain-English questions and get grounded answers from live BLS and Freddie Mac data via Snowflake Cortex and Dynamic Tables.">
</p>

## What it is

A conversational agent for US macroeconomic indicators. You ask in plain English — "What is the current unemployment rate?" or "How has inflation moved this year?" — and it answers from **live data** pulled into Snowflake, not from a model's memory.

It is built on three Snowflake capabilities:

- **Public free datasets** — BLS `FINANCIAL_ECONOMIC_INDICATORS_TIMESERIES` and Freddie Mac `FREDDIE_MAC_HOUSING_TIMESERIES`.
- **Dynamic Tables** — `prototype.py` shapes the raw feeds into one auto-refreshing `ECONOMIC_DASHBOARD_LIVE` table.
- **Cortex** — `streamlit_app.py` sends the live table plus your question to `SNOWFLAKE.CORTEX.COMPLETE`, which returns a concise answer that cites specific numbers and dates.

## How it works

<p align="center">
  <img src="./assets/readme/pipeline.svg" width="100%"
       alt="Pipeline: public BLS and Freddie Mac datasets are shaped into an auto-refreshing Dynamic Table, which a Streamlit app queries through Snowflake Cortex to return plain-English answers.">
</p>

1. **Ingest** — `prototype.py` reads the two public tables with Snowpark and extracts CPI, the unemployment rate, and the 30-year mortgage rate.
2. **Shape** — the three series are unioned, pivoted to one row per date, and promoted to a **Dynamic Table** that refreshes on a schedule.
3. **Ask** — `streamlit_app.py` loads the latest 24 rows, shows three live metric tiles, and opens a chat. Each question is wrapped with the data and sent to Cortex.
4. **Answer** — Cortex returns a short reply that formats rates as percentages (e.g. `4.1%`, not `0.041`) and quotes the underlying figures.

The agent also ships a second entry point, `ask_us_economy.py`, which uses **Cortex Analyst** against a Semantic View to turn a question into SQL, runs it with the Python connector, and prints the result.

## Getting started

### Prerequisites

- Python **3.13+** and [`uv`](https://docs.astral.sh/uv/)
- A Snowflake account with **Cortex** access and a warehouse
- Credentials for a role that can read the public datasets and create a Dynamic Table

### Install

```bash
uv sync
```

### Configure

Copy the example env file and fill in your Snowflake connection:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `SNOWFLAKE_ACCOUNT` | Account identifier (`<org>-<account>`) |
| `SNOWFLAKE_USER` / `SNOWFLAKE_PASSWORD` | Login credentials |
| `SNOWFLAKE_ROLE` | Role used for the session |
| `SNOWFLAKE_WAREHOUSE` | Compute warehouse |
| `SNOWFLAKE_DATABASE` / `SNOWFLAKE_SCHEMA` | Target database and schema |
| `SNOWFLAKE_SEMANTIC_VIEW` | Semantic View for the Cortex Analyst path |
| `SNOWFLAKE_CONNECTION_TTL` | Cache TTL for the Streamlit connection |

### Run the chat

```bash
uv run streamlit run streamlit_app.py
```

Open the URL Streamlit prints, then ask about unemployment, CPI, or mortgage rates.

### Run the Cortex Analyst path

```bash
uv run python ask_us_economy.py
```

## Project structure

| File | Role |
| --- | --- |
| `streamlit_app.py` | Chat UI + live metric tiles, backed by Cortex COMPLETE |
| `ask_us_economy.py` | Cortex Analyst → SQL → Python connector demo |
| `prototype.py` | Snowpark ingestion that builds `ECONOMIC_DASHBOARD_LIVE` |
| `cortex_response.py` | Parses Cortex Analyst message content; raises on errors |
| `test_cortex_response.py` | Unit test for the parser's error handling |
| `.env.example` | Template for required connection variables |

## How the chat stays grounded

The prompt sent to Cortex contains the actual rows from `ECONOMIC_DASHBOARD_LIVE` and explicit formatting rules, so answers stay tied to the data on screen:

> You are a US economic data analyst. Answer using ONLY this data. Be concise. Cite specific numbers and dates. Always format rate value to percentage…

## Limitations

- Answers depend entirely on the Dynamic Table's refresh schedule — stale data means stale answers.
- Requires Snowflake credentials and Cortex availability; there is no offline mode.
- `ask_us_economy.py` needs a configured Semantic View; without it the parser raises rather than returning empty content.

## License

This project does not yet ship a `LICENSE` file. Add one to define usage terms.
