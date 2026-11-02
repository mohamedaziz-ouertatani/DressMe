# Docker for the app (same environment for everyone) — design

Date: 2026-10-22. Status: approved, being built. Branch `feature/docker` (from main, after #60).

## Goal

Every teammate runs the app (MongoDB + backend + frontend) with the same Python,
PyTorch and package versions, without installing Python, PyTorch or MongoDB on their PC.
`docker compose up` starts it; the app is at http://localhost:5173.

## Decisions (with the user, 2026-10-22)

1. Scope = **run the app**: `mongo`, `backend`, `frontend`. The scripts in `src/`
   (training, evaluation, data pipeline) keep their current setup.
2. **Ollama stays on each PC** (approach A). The backend reaches it at
   `host.docker.internal:11434`. On a 4 GB GPU (RTX 2050) Ollama outside Docker already
   shares the card with the backend; two containers on one small card would be harder.
3. Shared through a **pull request**; the current (non-Docker) setup keeps working, and
   the README gets a new section, not a replacement.
4. **The image holds the environment, not the code or the data.** The repository is
   mounted into the containers, so code edits, `data/`, `models/` and `backend/.env`
   are read from the PC. The data and weights still come from a teammate (never in git,
   never in an image: academic licences, and too big).
5. **PyTorch is the CPU build by default** (decided after seeing the GPU image's size,
   ~3-4 GB of PyTorch + NVIDIA libraries): the app only runs the trained models on one
   photo at a time, which the CPU does in well under a second (the code already falls
   back to the CPU: `classifier.load_classifier`, `fashionclip.load_model`), and the GPU
   stays free for Ollama. The GPU build is opt-in (`docker-compose.gpu.yml`).

## What runs

| Service | Image | Port | Notes |
|---|---|---|---|
| `mongo` | `mongo:7.0` | 27017 | data in the `mongo-data` volume. pymongo 4.13 (pinned for the team's local MongoDB 4.0) supports 4.0 to 8.0 |
| `backend` | built from `docker/backend.Dockerfile` | 8000 | Python 3.13 + PyTorch (CPU build; GPU build opt-in) |
| `frontend` | built from `docker/frontend.Dockerfile` | 5173 | Node 24 + Vite dev server |

## Files

- `docker-compose.yml` — the three services and their volumes (backend on the CPU).
- `docker-compose.gpu.yml` — opt-in override: builds the GPU variant (`TORCH_INDEX` =
  the cu126 index, image `dressme-backend-gpu`) and requests the NVIDIA GPU.
- `docker/backend.Dockerfile` — `python:3.13-slim`, PyTorch `TORCH_VERSION` /
  `TORCHVISION_VERSION` from `TORCH_INDEX` (default: the CPU index), then the three
  requirement files with `docker/constraints.txt`.
- `docker/constraints.txt` — exact versions of every other package (`pip freeze` of a
  working image, without torch / torchvision, whose CPU and GPU builds carry different
  labels). `scikit-learn==1.6.1`: `models/checkpoints/colour_model.joblib` was saved
  with 1.6.1, and a scikit-learn pickle can break in another version.
- `docker/frontend.Dockerfile` — `node:24-slim`, `npm ci`.
- `docker/setup.ps1` — once per PC: creates `backend/.env` from `.env.example` (random
  `JWT_SECRET`, `CHAT_ENGINE=ollama`, `OLLAMA_MODEL=dressme-chat-v4`) if missing, registers
  `dressme-chat-v4` in Ollama from `models/llm/dressme-chat-v4/` if it is not registered,
  and lists the data / model files that are missing. Never overwrites an existing `.env`.
- `.dockerignore` — keeps `data/`, `models/`, `.venv/`, `node_modules/`, `.git/`,
  `backend/storage/` out of the build context.
- `README.md` — a "Run with Docker" section.

No application code changes: the backend already reads `MONGO_URL` / `OLLAMA_URL`
(`backend/app/config.py`), and the frontend proxy already reads `DRESSME_API`
(`frontend/vite.config.ts`).

## How the backend container is set up

- The repository is mounted at `/app`; the backend runs from `/app/backend` with
  `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`.
- Compose sets `MONGO_URL=mongodb://mongo:27017` and
  `OLLAMA_URL=http://host.docker.internal:11434`. These win over `backend/.env`
  (`load_dotenv` does not override variables that are already set), so the same `.env`
  works with and without Docker.
- `extra_hosts: host.docker.internal:host-gateway`, so the name also works on Linux.
- Model downloads (FashionCLIP from Hugging Face, rembg's U2-Net) go to the `model-cache`
  volume (`HF_HOME`, `U2NET_HOME`): downloaded once, kept across rebuilds.
- What the app writes lands on the PC as today: `backend/storage/` (uploads, collector
  logs), `mappings/` (Admin > Formula / Explainability "Save"), `data/raw/Listings/`.

## How the frontend container is set up

- The repository's `frontend/` is mounted; `node_modules` stays in the container (an
  anonymous volume), because the PC's copy is built for Windows.
- Vite runs with `--host 0.0.0.0` and `DRESSME_API=http://backend:8000`. The browser
  still talks only to http://localhost:5173.
- `CHOKIDAR_USEPOLLING=true` (every 0.3 s): Windows does not send file-change events into
  the container, so without it an edit is never seen (checked: the dev server kept
  serving the old file). Costs ~5% of one core.
- The backend has no auto-reload (models take ~1 min to load), as without Docker:
  `docker compose restart backend` after a backend change.

## Health checks

`mongo` is healthy when it answers a ping; `backend` when `/health` answers (after the
models are loaded). The backend waits for a healthy `mongo`, the frontend for a healthy
`backend`. The backend's `start_period` is 30 min: its first start downloads ~0.9 GB of
models (FashionCLIP, then rembg's two U2-Net models at start-up), ~20 min at 0.75 MB/s;
a 10 min limit failed on that connection.

## A teammate's steps

Once: install Docker Desktop and Ollama; clone; put the files from a teammate in `data/`
and `models/`; run `docker/setup.ps1`; `docker compose up --build` (first build a few
minutes); `docker compose exec backend python -m app.seed_demo` (demo accounts).
Every day: `docker compose up`, then http://localhost:5173.

## Checks (how we know it works)

1. `docker compose build` succeeds; the image has the CPU build of PyTorch, and a photo
   is analysed in about a second on the CPU.
2. The colour model loads with the pinned scikit-learn, without a version warning.
3. `docker compose up`: the backend logs "Application startup complete"; `GET /health`
   answers through the frontend proxy (`localhost:5173/api/health`).
4. The backend tests pass in the container against the `mongo` service
   (`docker compose exec backend python -m pytest`).
5. A chat message gets an answer from `dressme-chat-v4` through `host.docker.internal`.
6. `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build` starts
   with `torch.cuda.is_available()` True on a PC with an NVIDIA GPU.

## Out of scope

- Ollama in a container; the `src/` scripts in Docker; a production deployment (built
  frontend behind a web server, no source mounts). Each can follow later if the team
  wants it.
