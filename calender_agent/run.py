import os
import sys
import time
import uvicorn

# Ensure calendar_agent root directory is on Python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

class KeepAliveStdin:
    def read(self, *args, **kwargs):
        time.sleep(3600)
        return ""
    def readline(self, *args, **kwargs):
        time.sleep(3600)
        return ""
    def close(self, *args, **kwargs):
        pass
    def isatty(self, *args, **kwargs):
        return False

sys.stdin = KeepAliveStdin()

from calendar_agent.app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8005))
    uvicorn.run(app, host="127.0.0.1", port=port)
