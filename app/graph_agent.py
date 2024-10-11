import os
from tkinter import END
from typing import Annotated, TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.utils import get_db_connection_string, load_json_file
from pathlib import Path
import logging
import re
from langchain_community.utilities import SQLDatabase

# Set up logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Load messages from JSON file
messages = load_json_file(Path("config/messages.json"))

# Initialize the database connection
db = SQLDatabase.from_uri(get_db_connection_string())

# Initialize the language model
model = ChatOpenAI(model="gpt-4-mini", openai_api_base="https://openrouter.ai/api/v1",
                   openai_api_key=os.environ["OPENAI_API_KEY"])


class AgentState(TypedDict):
    messages: Annotated[list[HumanMessage | AIMessage], "The messages in the conversation"]
    next: Annotated[str, "The next function to call"]
    sql_query: Optional[str]
    query_result: Optional[List[Dict[str, Any]]]
    raw_sql: Optional[str]  # Add this line


def _extract_sql_query(response: str) -> Optional[str]:
    """
    Extract SQL query from the response string.

    Args:
    response (str): The response string containing the SQL query.

    Returns:
    Optional[str]: The extracted SQL query, or None if no query is found.
    """
    patterns: list[tuple[str, int]] = [
        (r'```sql\s*\n?SQLQuery:\s*(.*?)\n?```', re.DOTALL | re.IGNORECASE),
        (r'```sql\n(.*?)\n```', re.DOTALL),
        (r'SQLQuery:\s*(.*)', re.DOTALL)
    ]

    for pattern, flags in patterns:
        match = re.search(pattern, response, flags)
        if match:
            query = match.group(1).strip()
            return query

    logging.error(f"No SQL query found in the response: {response}")
    return None


def check_topic(state: AgentState) -> AgentState:
    logging.debug("Entering check_topic node")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an assistant that checks if a user's query is related to users, products, or orders in a sales system. Respond with 'YES' if it is, and 'NO' if it's not."),
        ("human", "{input}")
    ])
    response = model.invoke(prompt.format_messages(input=state["messages"][-1].content))
    if response.content.strip().upper() == "YES":
        state["next"] = "generate_sql"
        logging.debug("Query is related to the system. Moving to generate_sql")
    else:
        state["messages"].append(AIMessage(content=messages["TOPIC_FILTER_MESSAGE"]))
        state["next"] = "end"
        logging.debug("Query is not related to the system. Ending conversation")
    return state


def generate_sql(state: AgentState) -> AgentState:
    logging.debug("Entering generate_sql node")

    # Get the database schema
    db_schema = db.get_table_info()

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an SQL expert for PostgreSQL. Generate a safe SELECT query based on the user's request. 
        Use only PostgreSQL compatible functions and syntax. Wrap the SQL query in ```sql code blocks.
        Here's the database schema:
        {db_schema}
        Make sure to use the correct table and column names as specified in the schema."""),
        ("human", "{input}")
    ])
    response = model.invoke(prompt.format_messages(input=state["messages"][-1].content))
    extracted_query = _extract_sql_query(response.content)
    if extracted_query:
        state["sql_query"] = extracted_query
        state["raw_sql"] = response.content  # Store the full response
        state["next"] = "execute_sql"
        logging.debug(f"Generated SQL query: {state['sql_query']}")
    else:
        state["messages"].append(AIMessage(content="Failed to generate a valid SQL query."))
        state["next"] = "end"
        logging.error("Failed to extract SQL query from the response")
    return state


def is_safe_query(query: str) -> bool:
    unsafe_keywords = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'REPLACE']
    for keyword in unsafe_keywords:
        if re.search(r'\b' + keyword + r'\b', query, re.IGNORECASE):
            return False
    return True


def execute_sql(state: AgentState) -> AgentState:
    logging.debug("Entering execute_sql node")

    if not is_safe_query(state["sql_query"]):
        error_message = "The generated query contains potentially unsafe operations and cannot be executed."
        state["messages"].append(AIMessage(content=error_message))
        state["next"] = "end"
        logging.error(f"Attempted to execute unsafe query: {state['sql_query']}")
        return state

    try:
        result = db.run(state["sql_query"])
        if isinstance(result, list):
            # If the result is already a list of dicts, use it as is
            state["query_result"] = result
        elif isinstance(result, str):
            # If the result is a string (e.g., for COUNT queries), wrap it in a list of dict
            state["query_result"] = [{"result": result}]
        else:
            # For other types of results, attempt to convert to list of dicts
            state["query_result"] = [dict(row) for row in result]

        state["next"] = "format_response"
        logging.debug(f"SQL query executed successfully. Result: {state['query_result']}")
    except Exception as e:
        state["messages"].append(AIMessage(content=f"Error executing SQL query: {str(e)}"))
        state["next"] = "end"
        logging.error(f"Error executing SQL query: {str(e)}")
        logging.error(f"SQL Query: {state['sql_query']}")
        logging.error(f"Result type: {type(result)}")
        logging.error(f"Result: {result}")
    return state


def format_response(state: AgentState) -> AgentState:
    logging.debug("Entering format_response node")
    if not state.get("query_result"):
        state["messages"].append(
            AIMessage(content="I'm sorry, but I couldn't find any relevant information to answer your question."))
        state["next"] = "end"
        logging.debug("No query results to format. Ending conversation")
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant that provides clear and concise answers based on database query results. 
        Your task is to interpret the query results and respond to the user's original question in a natural, conversational manner. 
        Do not mention SQL, queries, or database operations in your response. 
        Instead, focus on providing a direct answer that addresses the user's question.
        If the result is a number, make sure to provide context about what that number represents.
        Use complete sentences and a friendly tone in your response."""),
        ("human", """Original question: {original_question}
        Query results: {query_result}
        Please provide a natural language answer to the original question based on these results:""")
    ])

    response = model.invoke(prompt.format_messages(
        original_question=state["messages"][0].content,
        query_result=state["query_result"]
    ))

    state["messages"].append(AIMessage(content=response.content))
    state["next"] = "end"
    logging.debug("Response formatted successfully")
    return state


# Create the graph
workflow = StateGraph(AgentState)

# Add nodes to the graph
workflow.add_node("check_topic", check_topic)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("format_response", format_response)

# Set the entry point
workflow.set_entry_point("check_topic")

# Add conditional edges
workflow.add_conditional_edges(
    "check_topic",
    lambda x: x["next"],
    {
        "generate_sql": "generate_sql",
        "end": END
    }
)

workflow.add_conditional_edges(
    "generate_sql",
    lambda x: x["next"],
    {
        "execute_sql": "execute_sql",
        "end": END
    }
)

workflow.add_conditional_edges(
    "execute_sql",
    lambda x: x["next"],
    {
        "format_response": "format_response",
        "end": END
    }
)

workflow.add_conditional_edges(
    "format_response",
    lambda x: "end",
    {
        "end": END
    }
)

# Compile the graph
app = workflow.compile()


def process_user_query(query: str) -> str:
    logging.info(f"Processing user query: {query}")
    initial_state = AgentState(
        messages=[HumanMessage(content=query)],
        next="",
        sql_query=None,
        query_result=None,
        original_question=query
    )
    final_state = app.invoke(initial_state)
    logging.info("Query processing completed")
    # Return the last message, which could be either the answer or the topic filter message
    return final_state["messages"][-1].content


# Example usage
if __name__ == "__main__":
    user_query = "How many users we have?"
    logging.info(f"Starting process with query: {user_query}")
    result = process_user_query(user_query)
    print(result)
    logging.info("Process completed")
