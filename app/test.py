import os
import re

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain.chains import create_sql_query_chain


def extract_sql_query(response):
    """
    Extract SQL query from the response string.
    
    Args:
    response (str): The response string containing the SQL query.
    
    Returns:
    str: The extracted SQL query, or None if no query is found.
    """
    sql_query = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
    if sql_query:
        return sql_query.group(1).strip()
    return None


db_url = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASS")}@{os.getenv("DB_HOST")}/{os.getenv("DB_NAME")}'

openai_api_key = os.environ.get("OPENAI_API_KEY")
# Extract SQL query from the response


db = SQLDatabase.from_uri(db_url)
llm = ChatOpenAI(
    model="gpt-4o-mini", openai_api_key=openai_api_key, openai_api_base='https://openrouter.ai/api/v1',
    temperature=0,
    verbose=True
    )

chain = create_sql_query_chain(llm, db,)

question = "What is total amount of sales in last year?"
response = chain.invoke({"question": question})

extracted_query = extract_sql_query(response)
if extracted_query:
    print("Extracted SQL query:")
    print(extracted_query)
else:
    print("No SQL query found in the response")
