"""
Create demo accounts for presentations: a user with a ready wardrobe of
dataset photos (labelled as demo data in the app), plus an admin.

Run from the backend/ folder while the API is running (it uploads through the
API, so every photo is really analysed):
    python -m app.seed_demo
    python -m app.seed_demo --api http://localhost:8000

The generated passwords are written to backend/.env (git-ignored) as
DEMO_EMAIL / DEMO_PASSWORD / DEMO_ADMIN_EMAIL / DEMO_ADMIN_PASSWORD, never
printed. Re-running reuses them and only adds missing wardrobe pieces.
"""

import argparse
import io
import secrets
import sys

import httpx
import pandas as pd
from dotenv import dotenv_values

from .config import BACKEND_DIR, SRC_DIRS, Settings
from .db import connect

sys.path[:0] = [str(d) for d in SRC_DIRS]
from item_images import DATA, load_item_image  # noqa: E402

ENV = BACKEND_DIR / ".env"
DEMO_EMAIL, ADMIN_EMAIL = "demo@example.com", "admin@example.com"
# a small, varied wardrobe: (category, how many)
PLAN = [("top", 5), ("bottom", 3), ("dress", 2), ("outerwear", 2), ("shoes", 3), ("bag", 2)]


def credentials():
    env = dotenv_values(ENV)
    creds = {k: env.get(k) or secrets.token_urlsafe(14)
             for k in ("DEMO_PASSWORD", "DEMO_ADMIN_PASSWORD")}
    missing = [k for k in creds if not env.get(k)]
    if missing:
        with open(ENV, "a", encoding="utf-8") as f:
            f.write("\n# demo accounts (python -m app.seed_demo)\n")
            f.write(f"DEMO_EMAIL={DEMO_EMAIL}\nDEMO_ADMIN_EMAIL={ADMIN_EMAIL}\n")
            for k in missing:
                f.write(f"{k}={creds[k]}\n")
    return creds


def token(client, email, password, name, gender):
    r = client.post("/auth/login", json={"email": email, "password": password})
    if r.status_code == 401:
        r = client.post("/auth/register", json={"email": email, "password": password, "name": name,
                                                "gender": gender})
    r.raise_for_status()
    return r.json()["token"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()
    creds = credentials()
    client = httpx.Client(base_url=args.api, timeout=120)

    demo = {"Authorization": f"Bearer {token(client, DEMO_EMAIL, creds['DEMO_PASSWORD'], 'Amira', 'women')}"}
    token(client, ADMIN_EMAIL, creds["DEMO_ADMIN_PASSWORD"], "Admin", "women")
    db = connect(Settings())
    db.users.update_one({"email": ADMIN_EMAIL}, {"$set": {"role": "admin"}})
    # the app labels these wardrobes as demo data (public-dataset photos)
    db.users.update_many({"email": {"$in": [DEMO_EMAIL, ADMIN_EMAIL]}}, {"$set": {"demo": True}})
    # the demo wardrobe is PolyVore pieces (mostly women's): REVIEW if the seed pieces change
    db.users.update_many({"email": {"$in": [DEMO_EMAIL, ADMIN_EMAIL]}, "profile.gender": None},
                         {"$set": {"profile.gender": "women"}})

    have = client.get("/items", headers=demo).json()
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "image_path", "bbox_x", "bbox_y", "bbox_w", "bbox_h",
                              "category", "split", "duplicate"])
    pv = df[(df["dataset"] == "polyvore") & (df["split"] == "test") & (df["duplicate"] != "True")]
    added = 0
    for category, n in PLAN:
        missing = n - sum(1 for i in have if i["category"] == category)
        for row in pv[pv["category"] == category].sample(max(missing, 0), random_state=11).to_dict("records"):
            buf = io.BytesIO()
            load_item_image(row).save(buf, format="JPEG", quality=90)
            r = client.post("/items", files={"photo": ("demo.jpg", buf.getvalue(), "image/jpeg")}, headers=demo)
            r.raise_for_status()
            added += 1
    print(f"Demo wardrobe ready ({added} pieces added). Accounts and passwords: see DEMO_* in {ENV}")


if __name__ == "__main__":
    main()
