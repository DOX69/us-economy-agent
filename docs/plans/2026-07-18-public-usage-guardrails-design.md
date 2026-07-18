# Public usage guardrails design

## Goal

Keep an anonymous Streamlit Community Cloud deployment useful while bounding Snowflake query and Cortex usage. Limits must be configurable, enforced before the costly call, and impossible to bypass through a page refresh.

## Request pipeline

1. Reject an empty, oversized, non-English or unsupported question locally.
2. Return the prior answer for an immediate duplicate without consuming quota.
3. Enforce the five-request Streamlit session allowance.
4. Acquire the process-wide two-request concurrency semaphore.
5. Atomically reserve one of the 50 daily requests in Snowflake and validate the full prompt's 3,000-token ceiling in the same statement.
6. Call `AI_COMPLETE` with a 1,000-token output ceiling.
7. Retain only the last successful exchange as future model context, while displaying the complete accepted session history.

A failed Cortex call after reservation remains chargeable. A quota-table error fails closed. No path, including an administrator session, bypasses these rules.

## Persistence and privacy

The singleton Snowflake quota row stores only its key, UTC date, count and update timestamp. Questions and answers remain in Streamlit session state and are not written to Snowflake or application logs.

## Data contract

The model receives 24 monthly snapshots. Each snapshot uses the latest non-null observation in that month for unemployment, CPI and the 30-year mortgage rate. This avoids spending prompt tokens on multiple source dates within one month.

## Configuration and deployment

Connection credentials, Cortex Analyst settings and tunable app limits live in Streamlit TOML secrets. The tracked example contains no credentials and is suitable as the Streamlit Community Cloud template. The real local secrets file remains ignored by Git.

## Operational boundaries

The quota protects Cortex calls, not every dashboard read. Cached monthly data limits dashboard queries. The implementation does not add IP tracking, cookies, Redis, Cortex Guard or an administrator override. Warehouse size and auto-suspend are inspected but not changed by the app.
