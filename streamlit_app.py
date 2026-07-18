# Streamlit app for exploring US economic indicators
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

local_connection = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "role": os.getenv("SNOWFLAKE_ROLE"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database": os.getenv("SNOWFLAKE_DATABASE"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA"),
}

if all(local_connection.values()):
    conn = st.connection(
        "local_snowflake",
        type="snowflake",
        ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"),
        **local_connection,
    )
else:
    conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

st.title("\U0001f4ca Ask the US Economy")
st.caption("Powered by Snowflake Cortex & Dynamic Tables \u2022 Data: BLS & Freddie Mac")

# Pull latest data from our auto-refreshing Dynamic Table
@st.cache_data(ttl=600)
def load_data():
    return session.sql(
        "SELECT * FROM ECONOMIC_DASHBOARD_LIVE ORDER BY DATE DESC LIMIT 24"
    ).to_pandas()

data = load_data()

# Show a quick snapshot
col1, col2, col3 = st.columns(3)
latest = data.dropna(subset=["UNEMPLOYMENT_RATE"]).iloc[0] if not data.empty else None
if latest is not None:
    col1.metric("Unemployment", f"{latest['UNEMPLOYMENT_RATE']*100:.1f}%")
latest_cpi = data.dropna(subset=["CPI"]).iloc[0] if not data.empty else None
if latest_cpi is not None:
    col2.metric("CPI Index", f"{latest_cpi['CPI']:.1f}")
latest_mort = data.dropna(subset=["MORTGAGE_RATE_30Y"]).iloc[0] if not data.empty else None
if latest_mort is not None:
    col3.metric("30Y Mortgage", f"{latest_mort['MORTGAGE_RATE_30Y']*100:.2f}%")

st.divider()

# Chat interface
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about unemployment, inflation, or mortgage rates..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            llm_prompt = f"""You are a US economic data analyst. Answer using ONLY this data.
Be concise. Cite specific numbers and dates. Always format rate value to percentage, examples: 4.1% good, _avoid_ 0.041. 

DATA:
{data.to_string(index=False)}

NOTES:
- CPI: Consumer Price Index (1982-84=100). Higher = more inflation.
- UNEMPLOYMENT_RATE: Decimal. 0.041 = 4.1%.
- MORTGAGE_RATE_30Y: Decimal. 0.0626 = 6.26%.

QUESTION: {prompt}"""

            answer = session.sql(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?)",
                params=["mistral-large2", llm_prompt]
            ).collect()[0][0]
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

with st.expander("\U0001f4cb View raw data"):
    st.dataframe(data, use_container_width=True)
