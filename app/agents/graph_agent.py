import logging
import re
from typing import Annotated, Any, Dict, List, Optional, Tuple, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from app.agents.agent import SQLAgent


class AgentState(TypedDict):
    messages: Annotated[list[HumanMessage | AIMessage], "The messages in the conversation"]
    next: Annotated[str, "The next function to call"]
    sql_query: Optional[str]
    query_result: Optional[List[Dict[str, Any]]]
    original_question: str


class GraphSQLAgent(SQLAgent):
    def __init__(
        self,
        db_url: str,
        llm_model: str = "gpt-4-mini",
        openai_api_base: str = 'https://openrouter.ai/api/v1'
    ) -> None:
        super().__init__(db_url, llm_model, openai_api_base)
        self.app = self._create_graph()

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("check_topic", self._node_check_topic)
        workflow.add_node("generate_sql", self._node_generate_sql)
        workflow.add_node("execute_sql", self._node_execute_sql)
        workflow.add_node("format_response", self._node_format_response)

        workflow.set_entry_point("check_topic")

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

        return workflow.compile()

    def _node_check_topic(self, state: AgentState) -> AgentState:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.prompts["GRAPH_TOPIC_FILTER_PROMPT"]),
            ("human", "{input}")
        ])
        response = self.llm.invoke(prompt.format_messages(input=state["messages"][-1].content))
        if response.content.strip().upper() == "YES":
            state["next"] = "generate_sql"
        else:
            state["messages"].append(AIMessage(content=self.messages["GRAPH_TOPIC_FILTER_MESSAGE"]))
            state["next"] = "end"
        return state

    def _node_generate_sql(self, state: AgentState) -> AgentState:
        db_schema = self.db.get_table_info()
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.prompts["GRAPH_SYSTEM_PROMPT"].format(db_schema=db_schema)),
            ("human", "{input}")
        ])
        response = self.llm.invoke(prompt.format_messages(input=state["messages"][-1].content))
        extracted_query = self._extract_sql_query(response.content)
        if extracted_query:
            state["sql_query"] = extracted_query
            state["next"] = "execute_sql"
        else:
            state["messages"].append(AIMessage(content="Failed to generate a valid SQL query."))
            state["next"] = "end"
        return state

    def _node_execute_sql(self, state: AgentState) -> AgentState:
        if not self._is_safe_query(state["sql_query"]):
            error_message = "The generated query contains potentially unsafe operations and cannot be executed."
            state["messages"].append(AIMessage(content=error_message))
            state["next"] = "end"
            return state

        try:
            result = self.db.run(state["sql_query"])
            if isinstance(result, list):
                state["query_result"] = result
            elif isinstance(result, str):
                state["query_result"] = [{"result": result}]
            else:
                state["query_result"] = [dict(row) for row in result]

            state["next"] = "format_response"
        except Exception as e:
            state["messages"].append(AIMessage(content=f"Error executing SQL query: {str(e)}"))
            state["next"] = "end"
        return state

    def _node_format_response(self, state: AgentState) -> AgentState:
        if not state.get("query_result"):
            state["messages"].append(AIMessage(content=self.messages["GRAPH_ERROR_MESSAGE"]))
            state["next"] = "end"
            return state

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.prompts["GRAPH_RESPONSE_FORMATTER_PROMPT"]),
            ("human", """Original question: {original_question}
            Query results: {query_result}
            Please provide a natural language answer to the original question based on these results:""")
        ])

        response = self.llm.invoke(prompt.format_messages(
            original_question=state["original_question"],
            query_result=state["query_result"]
        ))

        state["messages"].append(AIMessage(content=response.content))
        state["next"] = "end"
        return state

    def _is_safe_query(self, query: str) -> bool:
        unsafe_keywords = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'REPLACE']
        for keyword in unsafe_keywords:
            if re.search(r'\b' + keyword + r'\b', query, re.IGNORECASE):
                return False
        return True

    def query(self, question: str) -> Tuple[str, str]:
        try:
            initial_state = AgentState(
                messages=[HumanMessage(content=question)],
                next="",
                sql_query=None,
                query_result=None,
                original_question=question
            )
            final_state = self.app.invoke(initial_state)
            result = final_state["messages"][-1].content
            raw_sql = self.raw_sql
            return result, raw_sql
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return self.messages["GRAPH_ERROR_MESSAGE"], ""
