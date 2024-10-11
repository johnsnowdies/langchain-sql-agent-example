import os
from pathlib import Path
import re
import logging
from typing import Optional

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain.chains import create_sql_query_chain
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnableSerializable

from app.utils import load_json_file


class ChainSQLAgent:

    def __init__(
        self,
        db_url: str,
        llm_model: str = "gpt-4o-mini",
        openai_api_base: str = 'https://openrouter.ai/api/v1'
    ) -> None:
        """
        Initializes the SQLAgent with the given database URL, LLM model, and OpenAI API base.

        Args:
        db_url (str): The database URL.
        llm_model (str): The LLM model name.
        openai_api_base (str): The OpenAI API base URL.
        """
        parent_dir_path: Path = Path(__file__).parent.parent
        self.db: SQLDatabase = SQLDatabase.from_uri(db_url, sample_rows_in_table_info=3)
        self.llm: BaseLanguageModel = self._create_llm(llm_model, openai_api_base)
        self.prompts: dict[str, str] = load_json_file(parent_dir_path / 'config/prompts.json')
        self.messages: dict[str, str] = load_json_file(parent_dir_path / 'config/messages.json')
        self.chain: RunnableSerializable = self._create_chain()
        self.raw_sql = ''
        self.topic_filter_chain = self._create_topic_filter_chain()

    def _create_llm(self, model: str, api_base: str) -> ChatOpenAI:
        """
        Creates a ChatOpenAI instance with the specified model and API base.

        Args:
        model (str): The model name.
        api_base (str): The API base URL.

        Returns:
        ChatOpenAI: The created ChatOpenAI instance.
        """
        openai_api_key: Optional[str] = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        return ChatOpenAI(
            model=model,
            openai_api_key=openai_api_key,
            openai_api_base=api_base,
            verbose=True
        )

    def _create_chain(self) -> RunnableSerializable:
        answer_prompt: PromptTemplate = PromptTemplate.from_template(self.prompts['ANSWER_PROMPT'])
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
        prompt = ChatPromptTemplate.from_template(self.prompts['TOPIC_FILTER_PROMPT'])
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

    def _extract_sql_query(self, response: str) -> Optional[str]:
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
                self.raw_sql = query
                return query

        logging.error(f"No SQL query found in the response: {response}")
        return None

    def query(self, question: str) -> tuple[str, str]:
        """
        Executes a query on the database and returns the result and the raw SQL query.
        """
        try:
            if not self._is_relevant_question(question):
                return self.messages["TOPIC_FILTER_MESSAGE"], ""

            response: str = self.chain.invoke({"question": question})
            return response, self.raw_sql
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return self.messages["ERROR_MESSAGE"], ""
