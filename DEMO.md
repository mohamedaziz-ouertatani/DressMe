# DressMe — Jury demo script

About 8 minutes, one laptop, the team drives. Everything runs locally **except the Assistant (Gemini)**, so the demo survives a bad Wi-Fi.

## The day before

- [ ] `git pull` on `main`; `python -m pytest` in `backend/` passes; `npm run build` in `frontend/` passes.
- [ ] `backend/.env` has `JWT_SECRET` and a working `GEMINI_API_KEY` (send one real chat message to check the key and `GEMINI_MODEL`).
- [ ] `python -m app.seed_demo` (API running) → demo wardrobe of 17 PolyVore pieces + admin account; passwords are the `DEMO_*` lines in `backend/.env`. It also gives the admin its role.
- [ ] Look at the demo wardrobe, then pick **2 scan photos** (real friperie items, on a plain surface, whole piece in frame) and save them on the laptop:
  - **A — a near-twin** of something already owned (e.g. another black top) → expect **skip** + "you already own N similar pieces".
  - **B — a gap filler** (e.g. a jacket or bag that goes with several pieces) → expect **buy** or **think**.
  - Scan both once to check the verdicts; delete them from the wardrobe afterwards if you added them.
- [ ] Write down 2 chat questions that worked (see step 6).

## 30 minutes before

1. Start MongoDB (Windows service).
2. `cd backend` → `uvicorn app.main:create_app --factory --port 8000` (models load in ~1 min; wait for "Application startup complete").
3. `cd frontend` → `npm run dev` → open http://localhost:5173, log in as `demo@example.com`.
4. Open a second browser window (or private window) logged in as `admin@example.com` on `/admin`.
5. Browser zoom ~125 % so the jury can read it; close other tabs; notifications off.

## Run order

| # | Screen | What to do | What to say |
|---|---|---|---|
| 1 | **Login** | Show the language switch (English / Français / العربية). | Built for young Tunisians shopping second-hand: 56 % of our survey buy friperie, items are unlabelled and can't be returned. |
| 2 | **Wardrobe** | Scroll the pieces, open one item. | Each photo is analysed by our models: EfficientNet for category / type / pattern (95.7 % / 86.4 % / 86.8 % on test), a colour model, FashionCLIP for style. Dashed = guessed; the user taps to correct, and low-confidence colours are left for the user to confirm. |
| 3 | **Scan — photo A** | Choose from gallery → check fields → *Get the verdict*. | The question 42 % of our survey asked: "should I buy this?" Verdict **skip**: it doesn't beat what you own, and you already have similar pieces. |
| 4 | **Similar pieces** (from the verdict) | Show "Already in your wardrobe" and the H&M look-alikes. | FashionCLIP similarity search; the shop part is the H&M catalogue (63k products). |
| 5 | **Scan — photo B** | Same steps → verdict → scroll to "Best outfits with it". | Here it's **buy / think**: it makes good outfits where it beats every piece you own. Each outfit gets a 0-100 score with reasons. |
| 6 | **Assistant** | Ask e.g. "What can I wear with my jeans tomorrow?" then "Should I buy the last thing I scanned?" | Gemini, but it only talks about clothes the user really owns: it calls our functions (wardrobe, outfits, buy advice) instead of inventing. |
| 7 | **Build** | Pick a top + a bottom → score appears → add a suggested piece from "Complete it with". | The compatibility formula: style, colour, pattern, structure, weighted by the team. |
| 8 | **Today + Profile** | On Profile set modesty level 4, switch to العربية; back on Today change occasion. | Modesty and occasion filter every suggestion; the whole app mirrors right-to-left in Arabic. Switch back to English. |
| 9 | **Admin** (2nd window) | Overview → Model quality → Formula. | Usage per day; how often users correct each predicted field (where the models fail in real use); the team edits the formula weights live. |

Close on the numbers: classifier beats the FashionCLIP baseline on every field; outfit scoring reaches 78.7 % AUC on street photos (Fashionpedia). Limits, if asked: traditional wear and swimwear are too rare in public data (local photos are next), and style carries most of the scoring signal.

## If something goes wrong

| Problem | What to do |
|---|---|
| App shows "can't reach the server" | The API is down or still loading the models: check the uvicorn terminal, wait, press *Retry*. |
| Chat answers an error / no internet | Skip step 6; say it uses Gemini online. Everything else is local. |
| A scan gets a wrong label | Correct it on screen: that is the feature (step 2), and it shows up in Admin → Model quality. |
| Verdict differs from the rehearsal | Expected if the wardrobe changed; explain the rule (good outfits where the new piece beats what you own) and move on. |
| Port 8000 / 5173 busy | Close the old terminal, or start uvicorn with `--port 8001` and change the proxy target in `frontend/vite.config.ts`. |

**Don't** press *Save to CSV* on Admin → Formula during the demo: it rewrites `mappings/compatibility_weights.csv` at once.
