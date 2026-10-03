"""
Settings, read from environment variables (or backend/.env, never committed).

    MONGO_URL        default mongodb://localhost:27017
    MONGO_DB         default dressme
    JWT_SECRET       REQUIRED in real use: a long random string
    JWT_HOURS        how long a log-in lasts (default 72)
    GEMINI_API_KEY   for /chat (without it, /chat answers 503)
    GEMINI_MODEL     default gemini-3.8-flash (model names change: set it here)
    STORAGE_DIR      where uploaded photos go (default backend/storage)
    REMOVE_BACKGROUND  1 (default) = put uploaded photos on white before analysing them, 0 = off
    BACKGROUND_MODEL   rembg model for that (default u2net)
    CORS_ORIGINS     comma-separated, default http://localhost:5173 (React dev server)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


@dataclass
class Settings:
    mongo_url: str = field(default_factory=lambda: os.getenv("MONGO_URL", "mongodb://localhost:27017"))
    mongo_db: str = field(default_factory=lambda: os.getenv("MONGO_DB", "dressme"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_hours: int = field(default_factory=lambda: int(os.getenv("JWT_HOURS", "72")))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", BACKEND_DIR / "storage")))
    cors_origins: list = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", "http://localhost:5173").split(","))
    mappings_dir: Path = field(default_factory=lambda: ROOT / "mappings")   # formula CSVs
    max_upload_mb: int = 10
    max_image_side: int = 1024     # uploads are shrunk to save disk
    remove_background: bool = field(default_factory=lambda: os.getenv("REMOVE_BACKGROUND", "1") != "0")
    background_model: str = field(default_factory=lambda: os.getenv("BACKGROUND_MODEL", "u2net"))

    def check(self):
        if len(self.jwt_secret) < 32:
            raise RuntimeError("Set JWT_SECRET (at least 32 characters) in backend/.env")
