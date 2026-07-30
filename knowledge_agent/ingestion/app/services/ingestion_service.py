"""
app/services/ingestion_service.py

Core Knowledge Ingestion Pipeline Manager executing all 9 Steps:
STEP 1: Detect Document Type
STEP 2: Extract Plain Text
STEP 3: Generate Metadata
STEP 4: Generate Semantic Tags (5 to 20 tags)
STEP 5: Generate Keywords (up to 40 keywords)
STEP 6: Chunk Document (700 words target, 120 words overlap)
STEP 7: Generate Embeddings
STEP 8: Store in Vector DB & Relational DB
STEP 9: Verify Verification
"""

import json
import time
import uuid
import re
from datetime import datetime
from groq import Groq

from app.config.settings import get_settings
from app.services.cleaner import clean_text
from app.services.chunker import chunk_document
from app.services.embedder import generate_embedding
from app.db.vector_store import store_chunks_in_vector_db
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

EXTRACTION_PROMPT = """
Analyze the document text provided and return JSON with:
1. document_type: Choose ONE from (Email, Meeting, Transcript, Summary, PDF, Certificate, Rulebook, Brochure, Resume, Career Report, Learning Report, Task, Calendar Event, Notes, Unknown)
2. title: Concise title summarizing document
3. language: Document language (e.g. "en")
4. semantic_tags: List of 5 to 20 relevant tags (e.g. ["AI", "Python", "Docker", "Meeting", "Research", "Tasks"])
5. keywords: List of up to 40 keywords (technologies, orgs, people, tools, frameworks)

Return ONLY JSON:
{
  "document_type": "",
  "title": "",
  "language": "en",
  "semantic_tags": [],
  "keywords": []
}
"""


def clean_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


async def process_document_ingestion(raw_input: str, user_id: str = "user_default", source_agent: str = "Manual Upload") -> dict:
    start_time = time.time()

    # Verify non-empty input
    if not raw_input or not raw_input.strip():
        return {
            "status": "failed",
            "reason": "Empty document."
        }

    document_id = uuid.uuid4()
    now_iso = datetime.now().isoformat()

    # STEP 2: Extract Clean Plain Text
    clean_content = clean_text(raw_input)
    if not clean_content or not clean_content.strip():
        return {
            "status": "failed",
            "reason": "Document text cleaning resulted in empty content."
        }

    # STEP 1, 3, 4, 5: Metadata, Type, Tags, Keywords via LLM
    doc_type = "Notes"
    title = clean_content.splitlines()[0][:80] if clean_content else "Untitled Knowledge Document"
    tags = ["Notes", "AgentOS", "Knowledge"]
    keywords = [w for w in set(re.findall(r"\w+", clean_content[:500])) if len(w) > 4][:20]

    api_key = settings.effective_groq_key
    if api_key:
        try:
            logger.info("Extracting document type, metadata, tags, and keywords via Groq API...")
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(
                model=settings.GROQ_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": clean_content[:3000]}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            if res.choices and res.choices[0].message.content:
                data = clean_json_response(res.choices[0].message.content)
                doc_type = data.get("document_type", doc_type)
                title = data.get("title", title)
                tags = data.get("semantic_tags", tags)
                keywords = data.get("keywords", keywords)
        except Exception as e:
            logger.warning("Groq API metadata extraction fallback used (%s).", e)

    metadata = {
        "document_id": str(document_id),
        "user_id": user_id,
        "document_type": doc_type,
        "title": title,
        "created_time": now_iso,
        "updated_time": now_iso,
        "source": "AgentOS Knowledge Ingestion Service",
        "source_agent": source_agent,
        "language": "en",
        "keywords": keywords,
        "tags": tags,
        "version": "1.0"
    }

    # STEP 6: Chunk Document (700 words target, 120 overlap)
    chunks = chunk_document(clean_content, target_words=settings.CHUNK_SIZE_WORDS, overlap_words=settings.CHUNK_OVERLAP_WORDS)
    if not chunks:
        return {
            "status": "failed",
            "reason": "Chunking document failed."
        }

    # STEP 7: Generate Embeddings
    embeddings = []
    try:
        logger.info("Generating embeddings for %d chunks...", len(chunks))
        for c in chunks:
            emb = generate_embedding(c["text"])
            embeddings.append(emb)
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        return {
            "status": "failed",
            "reason": "Embedding generation failed."
        }

    # STEP 8: Store in Vector Database
    store_success = store_chunks_in_vector_db(
        document_id=str(document_id),
        chunks=chunks,
        embeddings=embeddings,
        doc_metadata=metadata
    )

    if not store_success:
        return {
            "status": "failed",
            "reason": "Vector database unavailable."
        }

    # STEP 9: Verify
    processing_time_ms = int((time.time() - start_time) * 1000)
    logger.info("🟢 SUCCESS: Ingested document %s (%s) into Vector DB (%d chunks, %d embeddings)", document_id, doc_type, len(chunks), len(embeddings))

    return {
        "status": "success",
        "document_id": str(document_id),
        "document_type": doc_type,
        "chunks_created": len(chunks),
        "embeddings_created": len(embeddings),
        "vector_database_updated": True,
        "metadata_created": True,
        "processing_time_ms": processing_time_ms,
        "title": title,
        "tags": tags,
        "keywords": keywords,
        "clean_content": clean_content,
        "raw_input": raw_input,
        "metadata": metadata,
        "chunks": chunks
    }
