"""
career_agent/server.py

Runner script for standalone Career Agent (Port 8002).
"""

import uvicorn

if __name__ == "__main__":
    print("Starting Career Agent server on http://127.0.0.1:8002...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
