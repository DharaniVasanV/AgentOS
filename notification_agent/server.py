"""
server.py

Uvicorn launcher for Notification Agent Version 3.0 on Port 8005.
"""

import uvicorn
from app.config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
