from pathlib import Path


SETUP_SQL = Path("sql/setup_quota.sql").read_text(encoding="utf-8")


def test_setup_grants_app_role_access_to_monthly_data():
    assert (
        "GRANT SELECT ON DYNAMIC TABLE "
        "ECON_AGENT_DB.ANALYTICS.ECONOMIC_DASHBOARD_LIVE "
        "TO ROLE US_ECONOMY_APP_ROLE;"
    ) in SETUP_SQL
