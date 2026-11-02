"""
The DressMe API (FastAPI).

Run from the backend/ folder (models load in ~1 min, then the API is ready):
    uvicorn app.main:create_app --factory --port 8000
Interactive documentation: http://localhost:8000/docs

`create_app` takes optional replacements for the models, the background remover,
the chat engine, the try-on engine, the weather and the price model, so the tests run in seconds with small fakes (see tests/conftest.py).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .background import load_remover
from .chat_engine import make_engine
from .config import Settings
from .db import connect
from .jobs import JobRunner
from .listings import ListingIndex, backfill_gender
from .routers import (admin, admin_xai, auth, chat, decisions, dress, explain, insights, items, listings, outfits,
                      tryon, vocab, wear, weather)
from .routers import price as price_routes
from .tryon import make_tryon
from .weather import make_weather


def create_app(settings=None, analyzer=None, catalog=None, chat_engine=None, remover=None,
               tryon_engine=None, weather_engine=None, price=None):
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
        classifier = getattr(app.state.analyzer, "classify_for_mask", None)
        app.state.remover = remover or load_remover(settings, classifier)   # None = keep backgrounds
        app.state.chat_engine = chat_engine or make_engine(settings)
        app.state.tryon = tryon_engine or make_tryon(settings)   # None = switched off
        app.state.weather = weather_engine or make_weather(settings)   # None = switched off
        if price is None:
            from price import make_price_model      # src/phase4/price.py (on the path through ml)
        app.state.price = price or make_price_model(settings)   # None = no model file yet
        app.state.listing_index = ListingIndex()
        backfill_gender(app.state.db)      # older listings get men / women / unisex
        app.state.jobs = JobRunner(app.state.db, settings.storage_dir)   # collector runs (admin)
        yield

    app = FastAPI(title="DressMe API", version="0.1", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])
    for r in (auth.router, items.router, explain.router, outfits.router, dress.router, decisions.router, insights.router, chat.router,
              listings.router, tryon.router, weather.router, vocab.router, wear.router, admin.router, admin_xai.router,
              price_routes.router):
        app.include_router(r)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
