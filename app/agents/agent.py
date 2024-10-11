import logging
import os
import re
from pathlib import Path
from typing import Optional

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from app.utils import load_json_file


class SQLAgent:
    def __init__(
        self,
        db_url: str,
        llm_model: str = "gpt-4-mini",
        openai_api_base: str = 'https://openrouter.ai/api/v1'
    ) -> None:
        """
        Initializes the SQLAgent with the given database URL, LLM model, and OpenAI API base.

        Args:
        db_url (str): The database URL.
        llm_model (str): The LLM model name.
        openai_api_base (str): The OpenAI API base URL.
        """
        parent_dir_path: Path = Path(__file__).parent.parent.parent
        self.db = SQLDatabase.from_uri(db_url)
        self.llm = self._create_llm(llm_model, openai_api_base)
        self.prompts = load_json_file(parent_dir_path / 'config/prompts.json')
        self.messages = load_json_file(parent_dir_path / 'config/messages.json')

    def _create_llm(self, model: str, api_base: str) -> ChatOpenAI:
        """
        Creates a ChatOpenAI instance with the specified model and API base.

        Args:
        model (str): The model name.
        api_base (str): The API base URL.

        Returns:
        ChatOpenAI: The created ChatOpenAI instance.
        """
        openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        return ChatOpenAI(
            model=model,
            openai_api_key=openai_api_key,
            openai_api_base=api_base,
            verbose=True
        )

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
