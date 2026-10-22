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

## What runs

| Service | Image | Port | Notes |
|---|---|---|---|
| `mongo` | `mongo:7.0` | 27017 | data in the `mongo-data` volume. pymongo 4.13 (pinned for the team's local MongoDB 4.0) supports 4.0 to 8.0 |
| `backend` | built from `docker/backend.Dockerfile` | 8000 | Python 3.13 + PyTorch cu126; GPU on by default |
| `frontend` | built from `docker/frontend.Dockerfile` | 5173 | Node 24 + Vite dev server |

## Files

- `docker-compose.yml` — the three services, volumes, GPU request.
- `docker-compose.cpu.yml` — override for a PC without an NVIDIA GPU (removes the GPU
  request; the models then run on the CPU, slower).
- `docker/backend.Dockerfile` — `python:3.13-slim`, PyTorch from the cu126 index, then
  the three requirement files with `docker/constraints.txt`.
- `docker/constraints.txt` — exact versions of every package (`pip freeze` of a working
  image). `scikit-learn==1.6.1`: `models/checkpoints/colour_model.joblib` was saved with
  1.6.1, and a scikit-learn pickle can break in another version.
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
- `npm run dev -- --host 0.0.0.0`, with `DRESSME_API=http://backend:8000`. The browser
  still talks only to http://localhost:5173.

## A teammate's steps

Once: install Docker Desktop and Ollama; clone; put the files from a teammate in `data/`
and `models/`; run `docker/setup.ps1`; `docker compose up --build` (first build ~10-20 min,
PyTorch is ~2.6 GB); `docker compose exec backend python -m app.seed_demo` (demo accounts).
Every day: `docker compose up`, then http://localhost:5173.

## Checks (how we know it works)

1. `docker compose build` succeeds; inside the image, `torch.cuda.is_available()` is True
   on a GPU PC.
2. The colour model loads with the pinned scikit-learn, without a version warning.
3. `docker compose up`: the backend logs "Application startup complete"; `GET /health`
   answers through the frontend proxy (`localhost:5173/api/health`).
4. The backend tests pass in the container against the `mongo` service
   (`docker compose exec backend python -m pytest`).
5. A chat message gets an answer from `dressme-chat-v4` through `host.docker.internal`.
6. `docker compose -f docker-compose.yml -f docker-compose.cpu.yml up` starts on the CPU.

## Out of scope

- Ollama in a container; the `src/` scripts in Docker; a production deployment (built
  frontend behind a web server, no source mounts). Each can follow later if the team
  wants it.
