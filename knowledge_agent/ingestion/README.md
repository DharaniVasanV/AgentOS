# Knowledge Ingestion Service - Knowledge Agent (AgentOS)

**Version 1.0**

The **Knowledge Ingestion Service** is an autonomous background engine inside the Knowledge Agent of AgentOS responsible for ingesting, cleaning, chunking, embedding, and indexing user documents into the AgentOS Vector Knowledge Base.

## 9-Step Pipeline
1. Document Type Detection
2. Plain Text Extraction & Noise Cleaning
3. Metadata Generation
4. Semantic Tag Generation (5 to 20 tags)
5. Keyword Extraction (up to 40 keywords)
6. Semantic Chunking (~700 words, ~120 words overlap)
7. Vector Embedding Generation (384-dimensional dense vectors)
8. Storage in Vector DB (ChromaDB) and PostgreSQL Relational Tables (`knowledge_documents`, `knowledge_chunks`, `knowledge_vectors`, `knowledge_metadata`, `agent_logs`)
9. Indexing Verification

## Output Response Format
```json
{
  "status": "success",
  "document_id": "",
  "document_type": "",
  "chunks_created": 0,
  "embeddings_created": 0,
  "vector_database_updated": true,
  "metadata_created": true,
  "processing_time_ms": 0
}
```

## Running locally

```bash
# 1. Initialize Relational Database
python init_db.py

# 2. Start Ingestion Server
python server.py
```
