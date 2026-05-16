"""
FastAPI entrypoint.

Run from project root:
    uvicorn backend.api:app --reload --port 8000
"""

from .app.main import app
