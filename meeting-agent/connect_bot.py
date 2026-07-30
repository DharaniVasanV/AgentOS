import asyncio
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.browser import connect_bot_session

if __name__ == "__main__":
    try:
        asyncio.run(connect_bot_session())
    except KeyboardInterrupt:
        pass
