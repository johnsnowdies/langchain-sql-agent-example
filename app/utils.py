import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote_plus


def get_db_connection_string() -> str:
    """
    Generates and returns a database connection string using environment variables.

    Returns:
    str: A formatted database connection string.

    Raises:
    ValueError: If any required environment variable is missing.
    """
    required_vars = ['DB_USER', 'DB_PASS', 'DB_HOST', 'DB_NAME']

    # Check if all required environment variables are set
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Environment variable {var} is not set")

    # Get values from environment variables
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASS')
    db_host = os.getenv('DB_HOST')
    db_name = os.getenv('DB_NAME')

    # URL encode the password to handle special characters
    encoded_pass = quote_plus(db_pass)

    # Construct and return the connection string
    return f'postgresql://{db_user}:{encoded_pass}@{db_host}/{db_name}'


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Loads a JSON file and returns its contents as a dictionary.

    Args:
    file_path (Path): The path to the JSON file.

    Returns:
    Dict[str, Any]: The contents of the JSON file as a dictionary.
    """
    try:
        with file_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {file_path}: {e}")
        raise
    except IOError as e:
        logging.error(f"Error reading file {file_path}: {e}")
        raise
