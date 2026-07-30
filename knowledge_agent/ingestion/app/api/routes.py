"""
app/api/routes.py

FastAPI REST routes for Knowledge Ingestion Service.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db import crud
from app.db.database import get_db
from app.services import ingestion_service

router = APIRouter()


class IngestRequest(BaseModel):
    content: str = Field(..., description="Raw document text to ingest")
    source_agent: str = Field("Manual Upload", description="Source agent name")
    user_id: str = Field("user_default", description="User ID")


@router.get("/health")
async def health():
    return {"status": "ok", "service": "Knowledge Ingestion Service", "version": "1.0"}


@router.post("/ingest")
async def ingest_document(
    req: IngestRequest,
    session: AsyncSession = Depends(get_db)
):
    result = await ingestion_service.process_document_ingestion(
        raw_input=req.content,
        user_id=req.user_id,
        source_agent=req.source_agent
    )

    if result.get("status") != "success":
        return result

    # Persist in PostgreSQL relational DB (optional/resilient)
    try:
        doc_id = uuid.UUID(result["document_id"])
        await crud.create_knowledge_entry(
            session=session,
            document_id=doc_id,
            user_id=req.user_id,
            document_type=result["document_type"],
            title=result["title"],
            source_agent=req.source_agent,
            raw_content=result["raw_input"],
            clean_content=result["clean_content"],
            chunks=result["chunks"],
            embeddings_count=result["embeddings_created"],
            meta=result["metadata"]
        )
    except Exception as err:
        pass

    return {
        "status": "success",
        "document_id": result["document_id"],
        "document_type": result["document_type"],
        "chunks_created": result["chunks_created"],
        "embeddings_created": result["embeddings_created"],
        "vector_database_updated": result["vector_database_updated"],
        "metadata_created": result["metadata_created"],
        "processing_time_ms": result["processing_time_ms"]
    }


@router.get("/documents")
async def list_documents(session: AsyncSession = Depends(get_db)):
    records = await crud.get_all_documents(session)
    return records


@router.get("/documents/{document_id}")
async def get_document(document_id: str, session: AsyncSession = Depends(get_db)):
    record = await crud.get_document(session, document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    return record


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, session: AsyncSession = Depends(get_db)):
    success = await crud.delete_document(session, document_id)
    return {"status": "deleted", "id": document_id}
