from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import tomllib


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class SnowflakeSettings:
    account: str
    user: str
    password: str
    role: str
    warehouse: str
    database: str
    schema: str


@dataclass(frozen=True)
class CortexAnalystSettings:
    semantic_view: str


@dataclass(frozen=True)
class AppSettings:
    model: str = "mistral-large2"
    daily_allowance: int = 50
    session_allowance: int = 5
    max_question_chars: int = 1000
    max_prompt_tokens: int = 3000
    max_output_tokens: int = 1000
    max_concurrent_requests: int = 2
    data_cache_ttl_seconds: int = 600
    connection_ttl_seconds: int = 3600
    quota_table: str = "ECON_AGENT_DB.ANALYTICS.APP_DAILY_QUOTA"


@dataclass(frozen=True)
class Settings:
    snowflake: SnowflakeSettings
    cortex_analyst: CortexAnalystSettings
    app: AppSettings


def _section(mapping: Mapping, name: str) -> dict:
    value = mapping[name]
    return dict(value)


def load_settings(secrets: Mapping) -> Settings:
    try:
        connection = _section(_section(secrets, "connections"), "snowflake")
        snowflake = SnowflakeSettings(
            **{field: connection[field] for field in SnowflakeSettings.__dataclass_fields__}
        )
        analyst = CortexAnalystSettings(**_section(secrets, "cortex_analyst"))
        app = AppSettings(**_section(secrets, "app"))
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError("Application configuration is incomplete.") from error

    limits = (
        app.daily_allowance,
        app.session_allowance,
        app.max_question_chars,
        app.max_prompt_tokens,
        app.max_output_tokens,
        app.max_concurrent_requests,
        app.data_cache_ttl_seconds,
        app.connection_ttl_seconds,
    )
    if any(value <= 0 for value in limits):
        raise ConfigError("Application configuration is incomplete.")
    return Settings(snowflake=snowflake, cortex_analyst=analyst, app=app)


def load_local_settings(path: str | Path = ".streamlit/secrets.toml") -> Settings:
    try:
        with Path(path).open("rb") as secrets_file:
            return load_settings(tomllib.load(secrets_file))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError("Application configuration is incomplete.") from error
