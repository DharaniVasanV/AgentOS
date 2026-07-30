"""
knowledge_agent/ingestion/server.py

Runner script for Knowledge Ingestion Service (Port 8003).
"""

import uvicorn

if __name__ == "__main__":
    print("Starting Knowledge Ingestion Service server on http://127.0.0.1:8003...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8003, reload=True)
