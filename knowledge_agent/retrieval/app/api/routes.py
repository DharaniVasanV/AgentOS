"""
app/api/routes.py

FastAPI REST routes for Knowledge Retrieval Service.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import retrieval_service

router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., description="User query text")


@router.get("/health")
async def health():
    return {"status": "ok", "service": "Knowledge Retrieval Service", "version": "1.0"}


@router.post("/query")
async def query_knowledge_base(req: QueryRequest):
    result = await retrieval_service.process_retrieval_query(req.query)
    return result
