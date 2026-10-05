"""
Settings, read from environment variables (or backend/.env, never committed).

    MONGO_URL        default mongodb://localhost:27017
    MONGO_DB         default dressme
    JWT_SECRET       REQUIRED in real use: a long random string
    JWT_HOURS        how long a log-in lasts (default 72)
    CHAT_ENGINE      gemini (default) or ollama (a local model, see LLM.md)
    OLLAMA_URL       default http://localhost:11434
    OLLAMA_MODEL     default qwen3:4b-instruct (our fine-tuned one: dressme-chat)
    OLLAMA_NUM_CTX   context window in tokens (default 8192: prompt + tools + history + tool answers)
    GEMINI_API_KEY   for /chat (without it, /chat answers 503)
    GEMINI_MODEL     default gemini-3.8-flash (model names change: set it here)
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
    chat_engine: str = field(default_factory=lambda: os.getenv("CHAT_ENGINE", "gemini").lower())
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct"))
    ollama_num_ctx: int = field(default_factory=lambda: int(os.getenv("OLLAMA_NUM_CTX", "8192")))
    ollama_timeout: float = 180.0      # seconds; the first answer also loads the model
    ollama_temperature: float = 0.3
    ollama_max_tokens: int = 600       # longest answer; stops a model that repeats itself forever
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
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
    mappings_dir: Path = field(default_factory=lambda: ROOT / "mappings")   # formula CSVs
    max_upload_mb: int = 10
    max_image_side: int = 1024     # uploads are shrunk to save disk
    remove_background: bool = field(default_factory=lambda: os.getenv("REMOVE_BACKGROUND", "1") != "0")
    background_model: str = field(default_factory=lambda: os.getenv("BACKGROUND_MODEL", "u2net"))
    cloth_model: str = field(default_factory=lambda: os.getenv("CLOTH_MODEL", "u2net_cloth_seg"))

    def check(self):
        if len(self.jwt_secret) < 32:
            raise RuntimeError("Set JWT_SECRET (at least 32 characters) in backend/.env")
