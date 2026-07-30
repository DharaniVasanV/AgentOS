# Research Agent - AgentOS

**Version 1.0**

The **Research Agent** is an autonomous AI agent within AgentOS responsible for understanding, analyzing, organizing, and extracting structured knowledge from any user-provided content.

## Features
- **19-Step Autonomous Data Extraction**:
  1. Content Type Identification
  2. Concise Title Generation
  3. Short Summary (3-6 sentences)
  4. Key Discussion Points (max 15)
  5. People & Roles Extraction
  6. Organizations Extraction
  7. Technologies Extraction
  8. URLs & Links Extraction
  9. Important Dates Extraction
  10. Tasks Extraction (Task, Assigned To, Deadline, Priority, Status, Description)
  11. Decisions Extraction (Decision, Reason, Impact)
  12. Risks Extraction
  13. Opportunities Extraction
  14. Keywords Extraction (max 30)
  15. Categories Extraction
  16. Missing Information Detection
  17. Recommended Next Agent Recommendation
  18. Confidence Score (0.0 to 1.0)
  19. Sentiment Estimation
- **Strict JSON Output**: Never hallucinates or fabricates data. Returns clean machine-readable JSON.
- **Multi-LLM Provider Engine**: Primary Google Gemini API with fallback to Groq Llama-3.3-70b.
- **Glassmorphic Web Dashboard**: Serve UI at `http://127.0.0.1:8001/`.

## Running locally

```bash
# 1. Initialize Database
python init_db.py

# 2. Start Research Agent
python server.py
```
