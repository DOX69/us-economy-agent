import requests
import snowflake.connector

from src.config.app_config import load_local_settings
from src.utils.cortex_response import extract_message_content

settings = load_local_settings()
ACCOUNT   = settings.snowflake.account
HOST      = f"{ACCOUNT}.snowflakecomputing.com"
USER      = settings.snowflake.user
PASSWORD  = settings.snowflake.password
SEMANTIC_VIEW = settings.cortex_analyst.semantic_view
WAREHOUSE = settings.snowflake.warehouse
DATABASE  = settings.snowflake.database
SCHEMA    = settings.snowflake.schema

# Step 1 - Get a session token for the REST API
login = requests.post(
    f"https://{HOST}/session/v1/login-request",
    json={"data": {"ACCOUNT_NAME": ACCOUNT, "LOGIN_NAME": USER, "PASSWORD": PASSWORD}},
    headers={"Content-Type": "application/json"},
)
token = login.json()["data"]["token"]

# Step 2 - Ask Cortex Analyst (REST API)
question = "What is the current unemployment rate?"
resp = requests.post(
    f"https://{HOST}/api/v2/cortex/analyst/message",
    json={
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "semantic_view": SEMANTIC_VIEW,
    },
    headers={"Authorization": f'Snowflake Token="{token}"', "Content-Type": "application/json"},
)

# Step 3 - Parse the response
data = resp.json()
sql_statement = None
for block in extract_message_content(data):
    if block["type"] == "text":
        print("Analyst:", block["text"])
    elif block["type"] == "sql":
        sql_statement = block["statement"]
        print(f"\nGenerated SQL:\n{sql_statement}")

# Step 4 - Execute the SQL with the Python connector
if sql_statement:
    conn = snowflake.connector.connect(
        account=ACCOUNT, user=USER, password=PASSWORD,
        warehouse=WAREHOUSE, database=DATABASE, schema=SCHEMA,
    )
    cur = conn.cursor()
    cur.execute(sql_statement)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print("\nResult:")
    print(" | ".join(cols))
    for row in rows:
        print(" | ".join(str(v) for v in row))
    cur.close()
    conn.close()
