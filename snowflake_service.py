from dataclasses import dataclass
from enum import Enum
import json
import re

from app_config import AppSettings


MONTHLY_DATA_SQL = """
SELECT
    DATE_TRUNC('MONTH', DATE)::DATE AS MONTH,
    MAX_BY(CPI, IFF(CPI IS NOT NULL, DATE, NULL)) AS CPI,
    MAX_BY(UNEMPLOYMENT_RATE, IFF(UNEMPLOYMENT_RATE IS NOT NULL, DATE, NULL))
        AS UNEMPLOYMENT_RATE,
    MAX_BY(MORTGAGE_RATE_30Y, IFF(MORTGAGE_RATE_30Y IS NOT NULL, DATE, NULL))
        AS MORTGAGE_RATE_30Y
FROM ECONOMIC_DASHBOARD_LIVE
GROUP BY 1
ORDER BY MONTH DESC
LIMIT 24
"""

UTC_DATE_SQL = "TO_DATE(CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()))"
IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*){2}$"
)


class ReservationStatus(Enum):
    RESERVED = "reserved"
    PROMPT_TOO_LARGE = "prompt_too_large"
    DAILY_LIMIT = "daily_limit"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ReservationResult:
    status: ReservationStatus
    error: Exception | None = None


def _quota_table(settings: AppSettings) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(settings.quota_table):
        raise ValueError("Invalid quota table identifier")
    return settings.quota_table


def _reservation_sql(table: str) -> str:
    return f"""
UPDATE {table}
SET
    REQUEST_COUNT = IFF(
        UTC_DATE = {UTC_DATE_SQL},
        REQUEST_COUNT + 1,
        1
    ),
    UTC_DATE = {UTC_DATE_SQL},
    UPDATED_AT = CURRENT_TIMESTAMP()
WHERE QUOTA_KEY = 'PUBLIC_CHAT'
  AND (UTC_DATE <> {UTC_DATE_SQL} OR REQUEST_COUNT < ?)
  AND AI_COUNT_TOKENS('ai_complete', ?, ?) <= ?
"""


def _diagnostic_sql(table: str) -> str:
    return f"""
SELECT
    AI_COUNT_TOKENS('ai_complete', ?, ?) AS PROMPT_TOKENS,
    REQUEST_COUNT
FROM {table}
WHERE QUOTA_KEY = 'PUBLIC_CHAT'
"""


def reserve_daily_allowance(
    session, settings: AppSettings, prompt: str
) -> ReservationResult:
    try:
        table = _quota_table(settings)
        updated = session.sql(
            _reservation_sql(table),
            params=[
                settings.daily_allowance,
                settings.model,
                prompt,
                settings.max_prompt_tokens,
            ],
        ).collect()
        if updated and int(updated[0][0]) == 1:
            return ReservationResult(ReservationStatus.RESERVED)

        diagnostic = session.sql(
            _diagnostic_sql(table), params=[settings.model, prompt]
        ).collect()
        if not diagnostic:
            return ReservationResult(ReservationStatus.UNAVAILABLE)
        if int(diagnostic[0][0]) > settings.max_prompt_tokens:
            return ReservationResult(ReservationStatus.PROMPT_TOO_LARGE)
        return ReservationResult(ReservationStatus.DAILY_LIMIT)
    except Exception as error:
        return ReservationResult(ReservationStatus.UNAVAILABLE, error)


def complete_answer(session, settings: AppSettings, prompt: str) -> str:
    result = session.sql(
        """
SELECT AI_COMPLETE(
    model => ?,
    prompt => ?,
    model_parameters => OBJECT_CONSTRUCT('temperature', 0, 'max_tokens', ?)
)
""",
        params=[settings.model, prompt, settings.max_output_tokens],
    ).collect()
    answer = str(result[0][0])
    try:
        decoded = json.loads(answer)
    except json.JSONDecodeError:
        return answer
    return decoded if isinstance(decoded, str) else answer
