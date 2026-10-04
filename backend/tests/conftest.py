"""
Test setup: the real FastAPI app with small FAKE models and a fake Gemini, on a
separate MongoDB database (dressme_test, emptied before and after each test).

The fake analyzer reads the photo's colour, so a test chooses what is
"recognised" by the colour of the picture it uploads:
    red -> top, blue -> bottom (jeans), black -> shoes, green -> dress, white -> bag
"""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pymongo import MongoClient

from app.config import Settings
from app.main import create_app

TEST_DB = "dressme_test"
FAKE = {  # rgb -> what the fake "model" answers
    (200, 30, 30): ("top", "t-shirt", "red"),
    (30, 60, 200): ("bottom", "jeans", "blue"),
    (10, 10, 10): ("shoes", "sneakers", "black"),
    (40, 160, 80): ("dress", "dress", "green"),
    (250, 250, 250): ("bag", "handbag", "white"),
}


def fake_vector(seed):
    v = np.random.default_rng(seed).normal(size=512) + 3.0   # all fairly similar
    return (v / np.linalg.norm(v)).astype(np.float32)


class FakeAnalyzer:
    def analyze(self, img):
        rgb = tuple(int(c) for c in np.asarray(img).reshape(-1, 3).mean(0).round())
        category, sub, colour = FAKE[min(FAKE, key=lambda k: sum(abs(a - b) for a, b in zip(k, rgb)))]
        return {"category": {"value": category, "conf": 0.95},
                "sub_category": {"value": sub, "conf": 0.9},
                "pattern": {"value": "solid", "conf": 0.8},
                "colour": {"value": colour, "conf": 0.9},
                "vector": fake_vector(sum(rgb))}


class FakeCatalog:
    def search(self, vector, k=6, category=None):
        return [{"id": f"pv_{i}", "category": category or "top", "sub_category": "",
                 "colour": "black", "score": 0.9 - i / 100} for i in range(k)]

    def search_shop(self, vector, k=6, category=None):
        return [{"id": f"hm_{i}", "name": f"Product {i}", "shop": "H&M", "department": "Menswear",
                 "category": category or "top", "sub_category": "", "colour": "navy",
                 "score": 0.8 - i / 100} for i in range(k)]

    def image(self, item_id):
        known = item_id.startswith(("pv_", "hm_"))
        return Image.new("RGB", (20, 20), (128, 128, 128)) if known else None


class FakeChatEngine:
    """Calls a tool when asked about the wardrobe or outfits, like Gemini would."""

    def reply(self, system, history, message, tools):
        if "wardrobe" in message:
            items = tools["list_wardrobe"]()
            return f"You have {len(items)} items.", ["list_wardrobe"]
        if "outfit" in message:
            outfits = tools["suggest_outfits"]()
            noun = "outfit" if len(outfits) == 1 else "outfits"
            return f"I found {len(outfits)} {noun}.", ["suggest_outfits"]
        if "buy" in message:
            advice = tools["buy_advice_last_scan"]()
            return f"Verdict: {advice.get('verdict', advice.get('error'))}", ["buy_advice_last_scan"]
        return f"(history {len(history)}) Hello!", []


class FakeTryOn:
    """Records each call and returns the person photo with a band of the
    garment's colour, so a test can see what was "put on" and in what order."""

    def __init__(self, fail_after=None):
        self.calls = []
        self.fail_after = fail_after     # raise TryOnBusy from this call number on

    def dress(self, person, garment, kind):
        from app.tryon import TryOnBusy
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise TryOnBusy("Space asleep")
        self.calls.append(kind)
        out = person.copy()
        out.paste(garment.resize((out.width, 8)), (0, 0))
        return out


def photo(rgb, size=(64, 80)):
    buf = io.BytesIO()
    Image.new("RGB", size, rgb).save(buf, format="PNG")
    return ("photo.png", buf.getvalue(), "image/png")


RED, BLUE, BLACK, GREEN, WHITE = FAKE


@pytest.fixture
def settings(tmp_path):
    # remove_background=False: no rembg in the tests unless a fake remover is passed
    return Settings(mongo_db=TEST_DB, jwt_secret="test-secret-" + "x" * 40,
                    gemini_api_key="", storage_dir=tmp_path / "storage", remove_background=False)


@pytest.fixture
def make_client(settings):
    MongoClient(settings.mongo_url).drop_database(TEST_DB)
    clients = []

    def make(chat_engine=None, remover=None, tryon=None):
        app = create_app(settings, analyzer=FakeAnalyzer(), catalog=FakeCatalog(),
                         chat_engine=chat_engine or FakeChatEngine(), remover=remover,
                         tryon_engine=tryon or FakeTryOn())
        c = TestClient(app)
        c.__enter__()            # runs the start-up (database connection)
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.__exit__(None, None, None)
    MongoClient(settings.mongo_url).drop_database(TEST_DB)


@pytest.fixture
def client(make_client):
    return make_client()


def sign_up(client, email="amira@example.com", name="Amira"):
    r = client.post("/auth/register", json={"email": email, "password": "secret-pass", "name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def upload(client, headers, rgb):
    r = client.post("/items", files={"photo": photo(rgb)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
