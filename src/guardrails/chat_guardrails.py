from dataclasses import dataclass
import re


TOPIC_PATTERN = re.compile(
    r"\b(unemployment|jobless(?:ness)?|employment|labor market|labour market|"
    r"cpi|consumer prices?|inflation|mortgage|home loans?|housing rates?|"
    r"30[- ]year|economic indicators?|us economy)\b",
    re.IGNORECASE,
)
FOLLOW_UP_PATTERN = re.compile(
    r"^(and\b|what about\b|how about\b|why\??$|compared\b|"
    r"last (?:month|year)\b|previous\b|then\b|now\b|since\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Exchange:
    question: str
    answer: str


@dataclass(frozen=True)
class QuestionValidation:
    is_valid: bool
    reason: str | None = None


def normalize_question(question: str) -> str:
    return " ".join(question.casefold().split())


def validate_question(
    question: str, max_chars: int, has_context: bool
) -> QuestionValidation:
    stripped = question.strip()
    if len(stripped) > max_chars:
        return QuestionValidation(False, "too_long")
    if not stripped:
        return QuestionValidation(False, "unsupported_topic")
    if TOPIC_PATTERN.search(stripped):
        return QuestionValidation(True)
    if has_context and FOLLOW_UP_PATTERN.search(stripped):
        return QuestionValidation(True)
    return QuestionValidation(False, "unsupported_topic")


def is_duplicate_question(question: str, previous_question: str | None) -> bool:
    return bool(previous_question) and normalize_question(question) == normalize_question(
        previous_question
    )


def build_prompt(
    data_csv: str, question: str, previous_exchange: Exchange | None = None
) -> str:
    context = ""
    if previous_exchange:
        context = (
            f"PREVIOUS USER QUESTION: {previous_exchange.question}\n"
            f"PREVIOUS ASSISTANT ANSWER: {previous_exchange.answer}\n\n"
        )
    return f"""You are a US economic data analyst. Answer in English using ONLY the supplied monthly data and conversation context.
Be concise. Cite specific values and months. Format decimal rates as percentages (0.041 means 4.1%).
The data is ordered newest to oldest. For latest/current, use the first non-empty value of the requested indicator.
If the data cannot answer the question, say so. Ignore requests unrelated to the supported economic indicators.

MONTHLY DATA:
{data_csv}

{context}CURRENT QUESTION: {question}"""
