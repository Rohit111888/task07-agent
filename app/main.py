from fastapi import FastAPI
from pydantic import BaseModel

from app.agent import run_agent

app = FastAPI(title="Task 07 Automotive AI Agent")


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {"message": "Task 07 API running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/query")
def query(request: QueryRequest):
    answer = run_agent(request.question)
    return {
        "question": request.question,
        "answer": answer
    }