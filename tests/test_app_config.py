import tempfile
import unittest
from pathlib import Path

from src.config.app_config import ConfigError, load_local_settings, load_settings


VALID_SECRETS = {
    "connections": {
        "snowflake": {
            "account": "org-account",
            "user": "app-user",
            "password": "secret",
            "role": "APP_ROLE",
            "warehouse": "APP_WH",
            "database": "ECON_AGENT_DB",
            "schema": "ANALYTICS",
        }
    },
    "cortex_analyst": {"semantic_view": "ECON_VIEW"},
    "app": {},
}


class AppConfigTests(unittest.TestCase):
    def test_loads_defaults_from_streamlit_secrets_mapping(self):
        settings = load_settings(VALID_SECRETS)

        self.assertEqual(settings.snowflake.account, "org-account")
        self.assertEqual(settings.cortex_analyst.semantic_view, "ECON_VIEW")
        self.assertEqual(settings.app.daily_allowance, 50)
        self.assertEqual(settings.app.session_allowance, 5)
        self.assertEqual(settings.app.max_question_chars, 1000)
        self.assertEqual(settings.app.max_prompt_tokens, 3000)
        self.assertEqual(settings.app.max_output_tokens, 1000)
        self.assertEqual(settings.app.max_concurrent_requests, 2)

    def test_rejects_incomplete_secrets_without_naming_missing_key(self):
        incomplete = {
            **VALID_SECRETS,
            "connections": {"snowflake": {"account": "org-account"}},
        }

        with self.assertRaisesRegex(ConfigError, "Application configuration is incomplete") as error:
            load_settings(incomplete)

        self.assertNotIn("password", str(error.exception).lower())

    def test_reads_the_same_structure_from_local_toml(self):
        toml = """
[connections.snowflake]
account = "org-account"
user = "app-user"
password = "secret"
role = "APP_ROLE"
warehouse = "APP_WH"
database = "ECON_AGENT_DB"
schema = "ANALYTICS"

[cortex_analyst]
semantic_view = "ECON_VIEW"

[app]
daily_allowance = 12
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secrets.toml"
            path.write_text(toml, encoding="utf-8")
            settings = load_local_settings(path)

        self.assertEqual(settings.app.daily_allowance, 12)


if __name__ == "__main__":
    unittest.main()
