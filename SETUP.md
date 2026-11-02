# DressMe — Setup guide (from zero to the running app)

This guide takes a Windows PC with nothing installed to the DressMe app open in the browser.
Follow the steps in order. Each step ends with a **Check** line: don't go on until it passes.

Time: about 1 hour the first time, most of it downloads. After that, starting the app takes one command.

How it runs: **Docker** runs three containers (MongoDB, the backend API, the frontend). **Ollama** runs
the chat model directly on your PC, outside Docker. Your code, `data/` and `models/` stay on your PC
and are shared with the containers, so you edit files normally.

```
your PC
├── Docker Desktop
│   ├── mongo     database               port 27017
│   ├── backend   FastAPI + the models    http://localhost:8000/docs
│   └── frontend  React app               http://localhost:5173   ← you open this
└── Ollama        the chat model (dressme-chat-v4)
```

---

## 0. What you need

- Windows 10 or 11, **16 GB of RAM** recommended (the models and the chat model together use a lot).
- About **15 GB of free disk**: Docker images, the files from the team (~3.5 GB), the model downloads.
- Access to the GitHub repository `mohamedaziz-ouertatani/DressMe` (ask the team if you can't open it).
- A good internet connection for the first start.

You do **not** need Python, Node.js or MongoDB on your PC: they all live inside Docker.

---

## 1. Install the tools

Install these three, in any order, with the default options:

| Tool | Download | Notes |
|---|---|---|
| Git | https://git-scm.com/download/win | Needed to clone the code. |
| Docker Desktop | https://www.docker.com/products/docker-desktop/ | Keep **"Use WSL 2"** ticked. It may ask you to restart the PC. |
| Ollama | https://ollama.com/download | Runs the chat model. It starts by itself and sits in the tray (bottom right). |

Then **start Docker Desktop** from the Start menu and wait until it says "Engine running"
(it does not always start by itself after a reboot).

**Check:** open **PowerShell** and run:

```powershell
git --version
docker --version
docker info
ollama --version
```

All four print a version or information, no error. If `docker info` fails with
"cannot find the file specified", Docker Desktop is not running yet: start it and wait.

---

## 2. Get the code

Pick a folder **without special characters** (for example `C:\Projects`) and clone:

```powershell
cd C:\Projects
git clone https://github.com/mohamedaziz-ouertatani/DressMe.git
cd DressMe
```

From now on, **every command runs in this `DressMe` folder**, in PowerShell.

**Check:** `dir` shows `backend`, `frontend`, `docker`, `mappings`, `src`, `docker-compose.yml`.

---

## 3. Get the files that are not in git

The trained models, the processed data and the chat model are too big for git, and the datasets
must never be redistributed, so they come from a teammate.

> **Where to get them:** _TODO: add the link to the team's shared folder here._
> Never upload these files anywhere public.

Put them in the cloned folder, **at exactly these paths**:

| Folder | Size | Needed for |
|---|---|---|
| `models\checkpoints\` (`classifier_best.pt`, `colour_model.joblib`, ...) | ~70 MB | **required**: photo analysis |
| `data\processed\` (with `dressme.csv`, `hm.csv`, the `embeddings\` folder, ...) | ~0.8 GB | **required**: similarity, look-alikes |
| `models\llm\dressme-chat-v4\` (`Modelfile` + `gguf\*.gguf`) | ~2.4 GB | the chat Assistant (see step 4 for other choices) |
| `data\raw\MarylandPolyVore\Re-PolyVore\`, `data\raw\FashionProduct\images\` | large | optional: pictures of look-alikes and the demo wardrobe |

**For the teammate who shares them:** from the `DressMe` folder of a PC where the app works, this
packs everything required into one file (Windows has `tar` built in, and it has no 2 GB limit):

```powershell
tar -cf dressme-files.tar models/checkpoints data/processed models/llm/dressme-chat-v4/Modelfile models/llm/dressme-chat-v4/gguf
```

The receiver copies `dressme-files.tar` into their `DressMe` folder and unpacks it there:

```powershell
tar -xf dressme-files.tar
```

**Check:** step 4's script lists every required file as `ok`.

---

## 4. Run the setup script (once per PC)

Make sure Docker Desktop is running, then:

```powershell
powershell -ExecutionPolicy Bypass -File docker\setup.ps1
```

It does three things, and running it again is safe:

1. creates `backend\.env` (your private settings, never committed) with a new secret key and the
   chat set to the local model. If `backend\.env` already exists, it leaves it alone;
2. registers the chat model `dressme-chat-v4` in Ollama;
3. lists the files from step 3 as `ok` or `MISSING`.

**Check:** it ends with **"Ready. Next: ..."**. If it says a required file is missing, go back to step 3.

**No chat model files?** The rest of the app works without them. For the chat you can either:

- use the base model instead: `ollama pull qwen3:4b-instruct`, then in `backend\.env` set
  `OLLAMA_MODEL=qwen3:4b-instruct`; or
- use Gemini (cloud): get a key at https://aistudio.google.com/, then in `backend\.env` set
  `CHAT_ENGINE=gemini` and `GEMINI_API_KEY=<your key>`. The free key allows only about 20 requests a
  day, and one answer costs 2 to 7, so keep chat tests rare.

---

## 5. Build and start the app

```powershell
docker compose up --build
```

The **first time is long** (about 15 to 30 minutes):

- Docker builds the images (Python, PyTorch, Node and every package, at fixed versions);
- the backend then downloads FashionCLIP and the background-removal models once (~0.9 GB, kept for
  next time);
- the frontend waits until the backend has loaded its models.

Leave this window open: it shows the logs. `Ctrl+C` stops the app.

**Check:** in a **second** PowerShell window:

```powershell
docker compose ps
```

`mongo` and `backend` say **(healthy)** and `frontend` is **Up**. Then open:

- http://localhost:5173 → the DressMe login page;
- http://localhost:8000/docs → the API documentation (optional).

---

## 6. First use

1. On http://localhost:5173, click **"New here? Create an account"**: name, email, password, gender, and tick the consent box.
   The account lives only in your local database.
2. Add a few clothes from **Wardrobe** (photos of single pieces on a plain background work best).
   Each photo is cleaned and analysed in a few seconds.
3. Try **Dress** (outfits for today), **Buy?** (should I buy this?) and the **Assistant** (chat).
   The first chat answer loads the model (~30 s); the next ones take 10-20 s.

Optional:

- **Admin pages:** give your account the admin role, then log in again and open `/admin`:
  ```powershell
  docker compose exec backend python -m app.make_admin you@example.com
  ```
- **Demo accounts** (`demo@example.com` with a ready wardrobe of 17 pieces, and `admin@example.com`).
  This needs the PolyVore pictures in `data\raw\` (step 3):
  ```powershell
  docker compose exec backend python -m app.seed_demo
  ```
  The passwords are written to `backend\.env` (the `DEMO_*` lines), never printed.
- **Shops** is empty on a new database: listings are collected from Admin > Listings (see `LISTINGS.md`).

**Check (everything at once):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_demo.ps1
```

Every line is `PASS` (Ollama can only be a `WARN`: the app works without it, the chat doesn't).

---

## 7. Every day

```powershell
# 1. start Docker Desktop and Ollama (tray icon), then:
docker compose up
# 2. open http://localhost:5173 (about 1 minute while the models load)
# 3. Ctrl+C to stop
```

| I want to... | Command |
|---|---|
| see what runs and whether it is healthy | `docker compose ps` |
| read the backend's logs | `docker compose logs -f backend` |
| apply a change in `backend\`, `src\` or `mappings\` | `docker compose up -d --build backend`, then wait ~1 min |
| apply a change in `frontend\` | nothing: the page reloads by itself |
| apply a change in `backend\.env` | `docker compose restart backend` |
| run the backend tests (~6 min) | `docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q` |
| get the team's latest code | `git pull`, then `docker compose up --build` |
| stop and remove the containers (data kept) | `docker compose down` |
| **delete** the database and the model downloads | `docker compose down -v` (careful: your accounts and wardrobe are gone) |

A backend that still runs old code answers **404 "Not Found"** on new pages or routes: rebuild it
with `docker compose up -d --build backend`.

Have an NVIDIA GPU? Photo analysis gets faster with the GPU image (~3-4 GB more to download):
`docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build`. The CPU version is
enough for the app.

---

## 8. When something goes wrong

| Problem | Fix |
|---|---|
| `docker info` / `docker compose` says "cannot find the file specified" or "pipe" | Docker Desktop is not running: start it and wait for "Engine running". |
| `port is already allocated` / `address already in use` on **27017** | A MongoDB installed on your PC is using the port. Stop it: PowerShell **as administrator**, `Stop-Service MongoDB` (and set it to Manual in `services.msc` so it doesn't come back). |
| ... on **8000** or **5173** | Another program (an old `uvicorn` or `npm run dev`) uses it: close that terminal. |
| `backend` stays "starting" for a long time | Normal the first time (it downloads ~0.9 GB). Watch `docker compose logs -f backend`. |
| `backend` is "unhealthy" or restarts | Read `docker compose logs backend`. Usually a missing file from step 3 (re-run `docker\setup.ps1` to see which) or no `JWT_SECRET` in `backend\.env`. |
| The page says it can't reach the server | The backend is down or still loading: wait, check `docker compose ps`, press Retry. |
| Chat: "Ollama is not running" / the assistant is off | Start Ollama from the Start menu, check `ollama list` shows `dressme-chat-v4`, send again. |
| Chat is very slow (> 1 min per answer) | Run `ollama ps`: if it says 100% CPU, quit Ollama from the tray and start it again (Ollama started while RAM was short misses the GPU). Close heavy programs. |
| Build fails while downloading packages | Network hiccup: run `docker compose up --build` again (finished parts are kept). |
| The disk is full | Docker Desktop > Troubleshoot > "Clean / Purge data" removes old images, or `docker system prune` (keeps volumes). |

Still stuck? Send the team the output of `docker compose ps` and `docker compose logs --tail 100 backend`.

---

## Where to read next

- `README.md`: what the project contains, the pipeline and the models.
- `CLAUDE.md`: the detailed project notes (every feature, rule and file).
- `LLM.md` (the chat model), `AGENTS.md` (the five chat agents), `LISTINGS.md` (shops and sellers), `DEMO.md` (the jury demo).
