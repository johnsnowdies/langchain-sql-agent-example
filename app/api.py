from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import SQLAgent
from app.utils import get_db_connection_string

app = FastAPI()


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    result: str
    raw_sql: str


@app.post("/query", response_model=QueryResponse)
def process_query(request: QueryRequest):
    agent = SQLAgent(get_db_connection_string())
    result, raw_sql = agent.query(request.query)
    return QueryResponse(result=result, raw_sql=raw_sql)
