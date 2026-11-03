"""
Settings, read from environment variables (or backend/.env, never committed).

    MONGO_URL        default mongodb://localhost:27017
    MONGO_DB         default dressme
    JWT_SECRET       REQUIRED in real use: a long random string
    JWT_HOURS        how long a log-in lasts (default 72)
    STORAGE_DIR      where uploaded photos go (default backend/storage)
    REMOVE_BACKGROUND  1 (default) = put uploaded photos on white before analysing them, 0 = off
    BACKGROUND_MODEL   rembg model for that (default u2net)
    CLOTH_MODEL        rembg model that keeps only the garment when it is worn
                       (default u2net_cloth_seg; empty = keep the whole person)
    TRYON_ENGINE     space (default: a Hugging Face Space, see tryon.py) or off
    TRYON_SPACES     Hugging Face Spaces tried in order (see tryon.py), comma-separated
    TRYON_STEPS      diffusion steps per garment (default 30: fewer = faster, rougher)
    HF_TOKEN         optional Hugging Face token: a bigger free GPU quota on the Space
    WEATHER_ENGINE   open-meteo (default, free, no key; see weather.py) or off
    WEATHER_LAT / WEATHER_LON / WEATHER_PLACE   place used when the app sends no position
                     (default Tunis: 36.81, 10.18)
    CORS_ORIGINS     comma-separated, default http://localhost:5173 (React dev server)
    CHAT_MODEL       the assistant's model in Ollama (default qwen3.5:4b; teammates may use dressme-chat-v4,
                     which is not evaluated: docs/superpowers/handoff/assistant-model.md)
    OLLAMA_URL       where Ollama answers (default http://host.docker.internal:11434 = the PC, seen from Docker)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
# the project code the API reuses (classifier, compatibility, connectors, ...)
SRC_DIRS = [ROOT / "src" / folder for folder in ("common", "phase3", "phase4")]
load_dotenv(BACKEND_DIR / ".env")


@dataclass
class Settings:
    mongo_url: str = field(default_factory=lambda: os.getenv("MONGO_URL", "mongodb://localhost:27017"))
    mongo_db: str = field(default_factory=lambda: os.getenv("MONGO_DB", "dressme"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_hours: int = field(default_factory=lambda: int(os.getenv("JWT_HOURS", "72")))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", BACKEND_DIR / "storage")))
    tryon_engine: str = field(default_factory=lambda: os.getenv("TRYON_ENGINE", "space").lower())
    tryon_spaces: str = field(default_factory=lambda: os.getenv(
        "TRYON_SPACES",
        "zhengchong/CatVTON, Kwai-Kolors/Kolors-Virtual-Try-On, yisol/IDM-VTON, levihsu/OOTDiffusion"))
    tryon_steps: int = field(default_factory=lambda: int(os.getenv("TRYON_STEPS", "30")))
    tryon_timeout: float = 180.0       # seconds per garment (a sleeping Space wakes up first)
    tryon_max_garments: int = 3        # chained garments per try-on (each costs GPU quota)
    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    weather_engine: str = field(default_factory=lambda: os.getenv("WEATHER_ENGINE", "open-meteo").lower())
    weather_lat: float = field(default_factory=lambda: float(os.getenv("WEATHER_LAT", "36.81")))
    weather_lon: float = field(default_factory=lambda: float(os.getenv("WEATHER_LON", "10.18")))
    weather_place: str = field(default_factory=lambda: os.getenv("WEATHER_PLACE", "Tunis"))
    cors_origins: list = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", "http://localhost:5173").split(","))
    chat_model: str = field(default_factory=lambda: os.getenv("CHAT_MODEL", "qwen3.5:4b"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://host.docker.internal:11434"))
    mappings_dir: Path =field(default_factory=lambda: ROOT / "mappings")   # formula CSVs
    max_upload_mb: int = 10
    max_image_side: int = 1024     # uploads are shrunk to save disk
    remove_background: bool = field(default_factory=lambda: os.getenv("REMOVE_BACKGROUND", "1") != "0")
    background_model: str = field(default_factory=lambda: os.getenv("BACKGROUND_MODEL", "u2net"))
    cloth_model: str = field(default_factory=lambda: os.getenv("CLOTH_MODEL", "u2net_cloth_seg"))

    def check(self):
        if len(self.jwt_secret) < 32:
            raise RuntimeError("Set JWT_SECRET (at least 32 characters) in backend/.env")
