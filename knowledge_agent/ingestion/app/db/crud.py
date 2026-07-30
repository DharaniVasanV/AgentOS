"""
app/db/crud.py

CRUD operations for Knowledge Base documents, chunks, vectors, metadata, and agent logs.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Sequence, Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import KnowledgeDocument, KnowledgeChunk, KnowledgeVector, KnowledgeMetadata, AgentLog

JSON_STORE_FILE = "e:/meeting-agent/knowledge_agent/ingestion/chroma_db/knowledge_store.json"


async def create_knowledge_entry(
    session: AsyncSession,
    document_id: uuid.UUID,
    user_id: str,
    document_type: str,
    title: str,
    source_agent: str,
    raw_content: str,
    clean_content: str,
    chunks: list[dict],
    embeddings_count: int,
    meta: dict,
) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        id=document_id,
        user_id=user_id,
        document_type=document_type,
        title=title,
        source_agent=source_agent,
        raw_content=raw_content,
        clean_content=clean_content,
        chunk_count=len(chunks),
        metadata_json=meta,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(doc)

    for idx, c in enumerate(chunks):
        chunk_id = uuid.uuid4()
        chunk_record = KnowledgeChunk(
            id=chunk_id,
            document_id=document_id,
            user_id=user_id,
            chunk_index=idx,
            chunk_text=c.get("text", ""),
            metadata_json=c.get("metadata", {}),
            created_at=datetime.now(),
        )
        session.add(chunk_record)

        vector_record = KnowledgeVector(
            id=uuid.uuid4(),
            chunk_id=chunk_id,
            document_id=document_id,
            vector_dim=384,
            created_at=datetime.now(),
        )
        session.add(vector_record)

    meta_record = KnowledgeMetadata(
        id=uuid.uuid4(),
        document_id=document_id,
        document_type=document_type,
        title=title,
        language=meta.get("language", "en"),
        keywords=meta.get("keywords", []),
        tags=meta.get("tags", []),
        created_at=datetime.now(),
    )
    session.add(meta_record)

    log_record = AgentLog(
        id=uuid.uuid4(),
        agent_name="Knowledge Ingestion Service",
        action="DOCUMENT_INGESTION",
        status="SUCCESS",
        details={
            "document_id": str(document_id),
            "document_type": document_type,
            "chunks_created": len(chunks),
            "embeddings_created": embeddings_count,
        },
        timestamp=datetime.now(),
    )
    session.add(log_record)

    await session.commit()
    await session.refresh(doc)
    return doc


async def get_all_documents(session: AsyncSession) -> List[Dict[str, Any]]:
    docs_list = []
    seen_ids = set()

    try:
        stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        res = await session.execute(stmt)
        pg_docs = res.scalars().all()
        for d in pg_docs:
            seen_ids.add(str(d.id))
            docs_list.append({
                "id": str(d.id),
                "document_type": d.document_type,
                "title": d.title,
                "source_agent": d.source_agent,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat() if d.created_at else ""
            })
    except Exception:
        pass

    if os.path.exists(JSON_STORE_FILE):
        try:
            with open(JSON_STORE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
            for item in items:
                doc_id = item.get("document_id")
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    meta = item.get("metadata", {})
                    docs_list.append({
                        "id": doc_id,
                        "document_type": meta.get("document_type", "Document"),
                        "title": item.get("document_name") or meta.get("title", "Ingested Document"),
                        "source_agent": meta.get("source_agent", "Manual Upload"),
                        "chunk_count": 1,
                        "created_at": meta.get("created_time", datetime.now().isoformat())
                    })
        except Exception:
            pass

    return docs_list


async def get_document(session: AsyncSession, doc_id: str) -> Optional[Dict[str, Any]]:
    # 1. Check PostgreSQL
    try:
        u_id = uuid.UUID(doc_id)
        doc = await session.get(KnowledgeDocument, u_id)
        if doc:
            return {
                "id": str(doc.id),
                "title": doc.title,
                "document_type": doc.document_type,
                "source_agent": doc.source_agent,
                "raw_content": doc.raw_content,
                "clean_content": doc.clean_content,
                "chunk_count": doc.chunk_count,
                "metadata_json": doc.metadata_json or {},
                "created_at": doc.created_at.isoformat() if doc.created_at else ""
            }
    except Exception:
        pass

    # 2. Check JSON store
    if os.path.exists(JSON_STORE_FILE):
        try:
            with open(JSON_STORE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
            matching_chunks = [i for i in items if i.get("document_id") == str(doc_id)]
            if matching_chunks:
                first = matching_chunks[0]
                meta = first.get("metadata", {})
                full_text = "\n\n".join(c.get("text", "") for c in matching_chunks)
                return {
                    "id": str(doc_id),
                    "title": first.get("document_name") or meta.get("title", "Knowledge Document"),
                    "document_type": meta.get("document_type", "Document"),
                    "source_agent": meta.get("source_agent", "Manual Upload"),
                    "raw_content": full_text,
                    "clean_content": full_text,
                    "chunk_count": len(matching_chunks),
                    "metadata_json": meta,
                    "created_at": meta.get("created_time", datetime.now().isoformat())
                }
        except Exception:
            pass

    return None


async def delete_document(session: AsyncSession, doc_id: str) -> bool:
    if os.path.exists(JSON_STORE_FILE):
        try:
            with open(JSON_STORE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
            filtered = [i for i in items if i.get("document_id") != str(doc_id)]
            with open(JSON_STORE_FILE, "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2)
        except Exception:
            pass

    try:
        u_id = uuid.UUID(doc_id)
        doc = await session.get(KnowledgeDocument, u_id)
        if doc:
            await session.delete(doc)
            await session.commit()
    except Exception:
        pass

    return True
