import os
from langchain_community.utilities import SQLDatabase
from langchain_anthropic import ChatAnthropic
from langchain.chains import create_sql_query_chain


db_url = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASS")}@{os.getenv("DB_HOST")}/{os.getenv("DB_NAME")}'
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")

db = SQLDatabase.from_uri(db_url)
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", anthropic_api_key=anthropic_api_key)
chain = create_sql_query_chain(llm, db)

question = "What is total amount of sales in last year?"
response = chain.invoke({"question": question})

print(response)
