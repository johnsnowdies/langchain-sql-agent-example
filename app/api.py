from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import create_chain, query_chain

app = FastAPI()


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    result: str


# Create the chain and db once when the app starts
chain, db = create_chain()


@app.post("/query", response_model=QueryResponse)
def process_query(request: QueryRequest):
    result = query_chain(chain, db, request.query)
    return QueryResponse(result=result)
