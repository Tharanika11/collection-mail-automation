import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
USE_GEMINI = os.getenv("USE_GEMINI", "true").strip().lower() == "true"


def has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def gemini_enabled() -> bool:
    return USE_GEMINI and has_gemini_key()