from fastapi import FastAPI
from pydantic import BaseModel

from app.agents.chain_agent import ChainSQLAgent
from app.agents.graph_agent import GraphSQLAgent
from app.utils import get_db_connection_string


app = FastAPI()


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    result: str
    raw_sql: str


@app.post("/chain_query", response_model=QueryResponse)
def process_chain_query(request: QueryRequest):
    agent = ChainSQLAgent(get_db_connection_string())
    result, raw_sql = agent.query(request.query)
    return QueryResponse(result=result, raw_sql=raw_sql)


@app.post("/graph_query", response_model=QueryResponse)
def process_graph_query(request: QueryRequest):
    agent = GraphSQLAgent(get_db_connection_string())
    result, raw_sql = agent.query(request.query)
    return QueryResponse(result=result, raw_sql=raw_sql)
