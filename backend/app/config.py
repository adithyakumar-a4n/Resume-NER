"""Application paths and environment-backed settings."""

from __future__ import annotations

import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"


def _configured_path(variable: str, default: str) -> Path:
    """Resolve configured paths relative to the backend directory."""
    configured = Path(os.getenv(variable, default)).expanduser()
    if not configured.is_absolute():
        configured = BACKEND_DIR / configured
    return configured.resolve()


DATABASE_PATH = _configured_path("DATABASE_PATH", "data/resume_ner.db")
UPLOAD_DIR = _configured_path("UPLOAD_DIR", "data/uploads")

SECRET_KEY = os.getenv(
    "SECRET_KEY", "DEV-ONLY-change-this-secret-before-deployment"
)
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
ENABLE_DEMO_ACCOUNTS = os.getenv("ENABLE_DEMO_ACCOUNTS", "false").strip().lower() == "true"

try:
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "12"))
except ValueError as exc:
    raise RuntimeError("MAX_UPLOAD_MB must be a positive integer.") from exc

if MAX_UPLOAD_MB < 1:
    raise RuntimeError("MAX_UPLOAD_MB must be a positive integer.")

DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
