from fastapi import FastAPI
from app.api import app as api_app

app = FastAPI()

# Include the routes from the api_app
app.include_router(api_app.router)
