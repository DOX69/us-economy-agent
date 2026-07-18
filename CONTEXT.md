# Public US Economy Assistant

This context defines the language used for the public conversational demo of US economic indicators.

## Language

**Supported indicator**:
One of the economic series the assistant can explain: unemployment rate, Consumer Price Index (CPI), or 30-year mortgage rate.
_Avoid_: Metric, arbitrary economic data

**Monthly snapshot**:
The latest available value of each supported indicator within a calendar month, used for comparisons across the most recent 24 months.
_Avoid_: Weekly series, arbitrary recent row

**Economic question**:
A visitor request about one or more supported indicators.
_Avoid_: Prompt, input, query

**Supported language**:
English is the language accepted for economic questions and used for assistant answers.
_Avoid_: Automatic translation, multilingual conversation

**Conversation session**:
A visitor's current sequence of economic questions and assistant answers.
_Avoid_: Account, user history

**Conversation context**:
The most recent completed economic question and answer available to interpret a follow-up question.
_Avoid_: Full history, memory

**Follow-up question**:
An economic question whose meaning depends on the conversation context; without that context, the same wording may be too ambiguous to accept.
_Avoid_: Standalone question

**Session allowance**:
The number of chargeable requests available within one conversation session.
_Avoid_: User quota, account quota

**Daily allowance**:
The shared number of chargeable requests available to all visitors during one UTC day.
_Avoid_: Session limit, token budget

**Chargeable request**:
An accepted economic question that reserves capacity for an AI answer, whether that answer succeeds or fails.
_Avoid_: Page refresh, rejected question

**Duplicate question**:
An economic question already answered in the same conversation context; it is not a new chargeable request.
_Avoid_: Follow-up question, retry after failure
