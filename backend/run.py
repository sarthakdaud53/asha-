import uvicorn
import os
import sys

# Ensure root directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.APP_NAME} on http://localhost:{settings.PORT} ...")
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
