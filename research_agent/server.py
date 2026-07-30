"""
research_agent/server.py

Runner script for standalone Research Agent (Port 8001).
"""

import uvicorn

if __name__ == "__main__":
    print("Starting Research Agent server on http://127.0.0.1:8001...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
