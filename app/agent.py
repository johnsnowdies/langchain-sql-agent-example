import os
from operator import itemgetter
from langchain_community.utilities import SQLDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from langchain.chains import create_sql_query_chain
schema_description = """
The database has the following tables:

1. orders
   - id: SERIAL (primary key)
   - date: DATE
   - quantity: INTEGER
   - amount: NUMERIC(10, 2)
   - product_id: INTEGER (foreign key to products.id)
   - user_id: INTEGER (foreign key to users.id)

2. products
   - id: SERIAL (primary key)
   - name: VARCHAR(255)

3. users
   - id: SERIAL (primary key)
   - email: VARCHAR(255)
   - full_name: VARCHAR(255)

The 'orders' table contains sales information, including the date of the order and the amount.
"""

answer_prompt = PromptTemplate.from_template(
    """Given the following user question, corresponding SQL query, and SQL result, answer the user question.
Question: Question here
SQLQuery: SQL Query to run
SQLResult: Result of the SQLQuery
Answer: Final answer here

Answer: """
)


db_url = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASS")}@{os.getenv("DB_HOST")}/{os.getenv("DB_NAME")}'


def create_chain():
    db = SQLDatabase.from_uri(db_url)
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
    llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", anthropic_api_key=anthropic_api_key)

    execute_query = QuerySQLDataBaseTool(db=db)
    write_query = create_sql_query_chain(llm, db)
    chain = (
        RunnablePassthrough.assign(query=write_query).assign(
            result=itemgetter("query") | execute_query
        )
        | answer_prompt
        | llm
        | StrOutputParser()
    )
    return chain, db


def query_chain(chain, db: SQLDatabase, query: str):
    try:
        response = chain.invoke({"question": query})
        """
        sql_query = response.sql_query
        result = db.run(sql_query)
        return f"SQL Query: {sql_query}\n\nResult: {result}"
        """
        return response
    except Exception as e:
        return f"An error occurred: {str(e)}"
