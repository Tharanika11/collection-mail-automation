import logging
import os
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash").strip()
USE_GEMINI = os.getenv("USE_GEMINI", "true").strip().lower() == "true"


def gemini_enabled() -> bool:
    return USE_GEMINI and bool(GEMINI_API_KEY)