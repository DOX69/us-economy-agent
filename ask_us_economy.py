import os

from dotenv import load_dotenv
import requests
import snowflake.connector

from cortex_response import extract_message_content

load_dotenv()

ACCOUNT   = os.getenv("SNOWFLAKE_ACCOUNT")
HOST      = f"{ACCOUNT}.snowflakecomputing.com"
USER      = os.getenv("SNOWFLAKE_USER")
PASSWORD  = os.getenv("SNOWFLAKE_PASSWORD")
SEMANTIC_VIEW = os.getenv("SNOWFLAKE_SEMANTIC_VIEW")
WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
DATABASE  = os.getenv("SNOWFLAKE_DATABASE")
SCHEMA    = os.getenv("SNOWFLAKE_SCHEMA")

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
