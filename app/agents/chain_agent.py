

import logging

from langchain.chains import create_sql_query_chain
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableSerializable

from app.agents.agent import SQLAgent


class ChainSQLAgent(SQLAgent):

    def __init__(
        self,
        db_url: str,
        llm_model: str = "gpt-4o-mini",
        openai_api_base: str = 'https://openrouter.ai/api/v1'
    ) -> None:
        super().__init__(db_url, llm_model, openai_api_base)
        self.chain: RunnableSerializable = self._create_chain()
        self.raw_sql = ''
        self.topic_filter_chain = self._create_topic_filter_chain()

    def _create_chain(self) -> RunnableSerializable:
        answer_prompt: PromptTemplate = PromptTemplate.from_template(self.prompts['CHAIN_ANSWER_PROMPT'])
        execute_query: QuerySQLDataBaseTool = QuerySQLDataBaseTool(db=self.db)
        write_query: RunnableSerializable = create_sql_query_chain(self.llm, self.db)
        return (
            RunnablePassthrough.assign(query=lambda x: self._extract_sql_query(write_query.invoke(x)))
            .assign(result=lambda x: self._execute_read_only_query(x["query"], execute_query))
            | answer_prompt
            | self.llm
            | StrOutputParser()
        )

    def _create_topic_filter_chain(self) -> RunnableSerializable:
        """
        Creates a chain to filter out questions not related to the sales system.
        """
        prompt = ChatPromptTemplate.from_template(self.prompts['CHAIN_TOPIC_FILTER_PROMPT'])
        return prompt | self.llm | StrOutputParser()

    def _execute_read_only_query(self, query: str, execute_query: QuerySQLDataBaseTool) -> str:
        """
        Execute the query in read-only mode.
        """
        if self._is_read_only_query(query):
            return execute_query.run(query)
        else:
            return "This query is not allowed as it may modify the database. Only SELECT statements are permitted."

    def _is_read_only_query(self, query: str) -> bool:
        """
        Check if the query is read-only (SELECT statement).
        """
        return query.strip().lower().startswith("select")

    def _is_relevant_question(self, question: str) -> bool:
        """
        Checks if the question is relevant to the sales system.
        """
        response = self.topic_filter_chain.invoke({"question": question})
        logging.info(f"Topic filter response: {response}")
        return response.strip().lower() == "yes"

    def query(self, question: str) -> tuple[str, str]:
        """
        Executes a query on the database and returns the result and the raw SQL query.
        """
        try:
            if not self._is_relevant_question(question):
                return self.messages["CHAIN_TOPIC_FILTER_MESSAGE"], ""

            response: str = self.chain.invoke({"question": question})
            return response, self.raw_sql
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return self.messages["CHAIN_ERROR_MESSAGE"], ""
