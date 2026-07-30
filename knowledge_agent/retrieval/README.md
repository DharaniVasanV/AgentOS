# Knowledge Retrieval Service - Knowledge Agent (AgentOS)

**Version 1.0**

The **Knowledge Retrieval Service** is an autonomous RAG engine inside the Knowledge Agent of AgentOS responsible for querying vector embeddings from ChromaDB, retrieving relevant context, generating grounded answers using `GROQ_API_KEY5`, and returning structured citations.

## 12-Step RAG Retrieval Pipeline
1. Receive User Query
2. Query Validation
3. Query Embedding Generation (384-dimensional dense vectors)
4. Vector Database Search (ChromaDB Cosine Similarity)
5. Retrieve Top 5 Chunks
6. Filter & Sort (Highest Similarity First)
7. Context Building
8. Final Prompt Generation to Groq API Key 5 (`GROQ_API_KEY5`)
9. Groq Grounded Response Generation
10. Citation Generation
11. Confidence Estimation (`High` > 0.90, `Medium` 0.80-0.90, `Low` < 0.80)
12. Grounded JSON Response Output

## API Key & Model
Configured to use `GROQ_API_KEY5` (`llama-3.3-70b-versatile`).

## Running locally

```bash
# Start Knowledge Retrieval Service Server
python server.py
```
