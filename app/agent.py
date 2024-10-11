import os
import re
import logging
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain.chains import create_sql_query_chain

db_url = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASS")}@{os.getenv("DB_HOST")}/{os.getenv("DB_NAME")}'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ANSWER_PROMPT = """Given the following user question, corresponding SQL query, and SQL result, answer the user question.
Question: {question}
SQL Query: {query}
SQL Result: {result}
Answer: """


def extract_sql_query(response):
    """
    Extract SQL query from the response string.

    Args:
    response (str): The response string containing the SQL query.

    Returns:
    str: The extracted SQL query, or None if no query is found.
    """
    # Log the extraction attempt
    logger.info(f"Attempting to extract SQL query from response: {response}")

    # Try to extract SQL query with markdown and SQLQuery inside
    sql_query = re.search(r'```sql\s*\n?SQLQuery:\s*(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
    if sql_query:
        logger.info(f"SQL query found with markdown and SQLQuery prefix: {sql_query.group(1).strip()}")
        return sql_query.group(1).strip()

    # Try to extract SQL query with markdown
    sql_query = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
    if sql_query:
        logger.info(f"SQL query found with markdown: {sql_query.group(1).strip()}")
        return sql_query.group(1).strip()

    # If not found, try to extract SQL query without markdown
    sql_query = re.search(r'SQLQuery:\s*(.*)', response, re.DOTALL)
    if sql_query:
        logger.info(f"SQL query found without markdown: {sql_query.group(1).strip()}")
        return sql_query.group(1).strip()

    logger.info("No SQL query found in the response")
    return None


def create_chain():
    db = SQLDatabase.from_uri(db_url)
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=openai_api_key,
        openai_api_base='https://openrouter.ai/api/v1',
        verbose=True
    )
    answer_prompt = PromptTemplate.from_template(ANSWER_PROMPT)
    execute_query = QuerySQLDataBaseTool(db=db)
    write_query = create_sql_query_chain(llm, db)
    chain = (
        RunnablePassthrough.assign(query=lambda x: extract_sql_query(write_query.invoke(x)))
        .assign(result=lambda x: execute_query.run(x["query"]))
        | answer_prompt
        | llm
        | StrOutputParser()
    )
    return chain, db


def query_chain(chain, db: SQLDatabase, query: str):
    try:
        response = chain.invoke({"question": query})
        return response
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return "Sorry, I couldn't find the answer to your question. Rephrase your question and try again, please."
