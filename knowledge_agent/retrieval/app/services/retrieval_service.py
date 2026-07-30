"""
app/services/retrieval_service.py

Core Knowledge Retrieval Service executing all 12 RAG steps with GROQ_API_KEY5.
"""

import json
import time
import re
from groq import Groq

from app.config.settings import get_settings
from app.services.embedder import generate_query_embedding
from app.db.vector_search import search_vector_database
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """
You are an AI Knowledge Assistant.
Answer ONLY using the supplied context.
Never use outside knowledge.
Never guess.
Never hallucinate.
If the answer is not present inside the retrieved context, reply:
"I could not find sufficient information inside the AgentOS Knowledge Base."
Always answer in clear English.
If multiple retrieved documents disagree, mention the conflict.
Always preserve names, dates and facts exactly.
"""


async def process_retrieval_query(user_query: str) -> dict:
    start_time = time.time()

    # STEP 2: Validate Query
    if not user_query or not user_query.strip():
        return {
            "status": "failed",
            "reason": "Empty query."
        }

    # STEP 3: Generate Query Embedding (No LLM)
    try:
        logger.info("STEP 3: Generating query embedding...")
        query_vec = generate_query_embedding(user_query)
    except Exception as e:
        logger.error("Query embedding failed: %s", e)
        return {
            "status": "failed",
            "reason": "Query embedding generation failed."
        }

    # STEP 4 & 5: Search Vector Database & Retrieve Top 5 Results
    try:
        logger.info("STEP 4 & 5: Searching vector DB with Cosine Similarity...")
        retrieved_chunks = search_vector_database(user_query, query_vec, top_k=settings.TOP_K)
    except Exception as e:
        logger.error("Vector DB search failed: %s", e)
        return {
            "status": "failed",
            "reason": "Vector database unavailable."
        }

    # STEP 6: Filter & Sort Results
    filtered_chunks = [c for c in retrieved_chunks if c["similarity_score"] >= settings.SIMILARITY_THRESHOLD]
    
    if not filtered_chunks and retrieved_chunks:
        # Include top result if available to ensure best-effort context
        filtered_chunks = retrieved_chunks[:3]

    # Handle NOTHING FOUND case
    if not filtered_chunks:
        processing_time_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "success",
            "query": user_query,
            "answer": "I could not find sufficient information inside the AgentOS Knowledge Base.",
            "retrieved_documents": [],
            "citations": [],
            "confidence": "Low",
            "processing_time_ms": processing_time_ms
        }

    # STEP 7: Build Retrieval Context
    context_blocks = []
    for idx, chunk in enumerate(filtered_chunks):
        block = f"[DOCUMENT {idx+1}: {chunk['document_name']} (ID: {chunk['document_id']})]\n{chunk['original_text']}"
        context_blocks.append(block)

    context_str = "\n\n".join(context_blocks)

    # STEP 8: Generate Final Prompt & Call Groq API Key 5
    api_key = settings.effective_groq_key
    if not api_key:
        return {
            "status": "failed",
            "reason": "Answer generation failed."
        }

    try:
        logger.info("STEP 8 & 9: Generating grounded response via Groq API Key 5 (%s)...", settings.GROQ_CHAT_MODEL)
        client = Groq(api_key=api_key)
        user_prompt = f"Question:\n{user_query}\n\nRetrieved Context:\n{context_str}"

        res = client.chat.completions.create(
            model=settings.GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1
        )

        if res.choices and res.choices[0].message.content:
            answer = res.choices[0].message.content.strip()
        else:
            answer = "I could not find sufficient information inside the AgentOS Knowledge Base."
    except Exception as e:
        logger.error("Groq API Key 5 answer generation failed: %s", e)
        return {
            "status": "failed",
            "reason": "Answer generation failed."
        }

    # STEP 10: Generate Citations & Document Metadata
    retrieved_documents = []
    citations = []
    max_sim = 0.0

    for c in filtered_chunks:
        sim = c["similarity_score"]
        if sim > max_sim:
            max_sim = sim

        retrieved_documents.append({
            "document_id": c["document_id"],
            "document_name": c["document_name"],
            "chunk_id": c["chunk_id"],
            "similarity_score": sim
        })

        citations.append({
            "document": c["document_name"],
            "chunk": c["chunk_id"],
            "source": "Knowledge Base"
        })

    # STEP 11: Estimate Confidence
    if max_sim >= 0.90:
        confidence = "High"
    elif max_sim >= 0.80:
        confidence = "Medium"
    else:
        confidence = "Low"

    processing_time_ms = int((time.time() - start_time) * 1000)

    # STEP 12: Return JSON
    logger.info("🟢 SUCCESS: RAG Retrieval query processed in %d ms (Confidence: %s)", processing_time_ms, confidence)
    return {
        "status": "success",
        "query": user_query,
        "answer": answer,
        "retrieved_documents": retrieved_documents,
        "citations": citations,
        "confidence": confidence,
        "processing_time_ms": processing_time_ms
    }
