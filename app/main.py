import logging
import os

from fastapi import FastAPI

from app.api import app as api_app


# Setup logging
logging_level = os.environ.get('LOGGING_LEVEL', 'INFO')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, logging_level.upper())
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("langgraph").setLevel(logging.INFO)  # Добавлено логирование для LangGraph

app = FastAPI()

# Include the routes from the api_app
app.include_router(api_app.router)
