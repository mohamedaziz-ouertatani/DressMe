"""
The DressMe API (FastAPI).

Run from the backend/ folder (models load in ~1 min, then the API is ready):
    uvicorn app.main:create_app --factory --port 8000
Interactive documentation: http://localhost:8000/docs

`create_app` takes optional replacements for the models and Gemini, so the
tests run in seconds with small fakes (see tests/conftest.py).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chat_engine import GeminiEngine
from .config import Settings
from .db import connect
from .routers import auth, chat, items, outfits


def create_app(settings=None, analyzer=None, catalog=None, chat_engine=None):
    settings = settings or Settings()
    settings.check()

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings
        app.state.db = connect(settings)
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        if analyzer is None or catalog is None:
            from .ml import Analyzer, Catalog      # the real models (slow to load)
        app.state.analyzer = analyzer or Analyzer()
        app.state.catalog = catalog or Catalog()
        app.state.chat_engine = chat_engine or GeminiEngine(settings)
        yield

    app = FastAPI(title="DressMe API", version="0.1", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])
    for r in (auth.router, items.router, outfits.router, chat.router):
        app.include_router(r)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

