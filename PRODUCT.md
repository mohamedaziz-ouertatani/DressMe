# Product

## Platform

web

## Stack

React + TailwindCSS frontend (fixed by the project plan), talking to the FastAPI + MongoDB backend in `backend/` (see README "Phase 4: backend API"). Lives in `frontend/`.

## Users

Young Tunisians (students and young workers) on a limited budget who buy mostly second-hand clothes in friperies. Items are often unlabelled (no size, brand or composition) and can rarely be returned, so every purchase is a small gamble. Personas from Phase 1: Amira, Youssef, Nour, Rania, Salma, Ines, Skander.

Survey (57 responses): black dominates 84% of wardrobes, 56% shop second-hand, 40% are frustrated by fit, 42% want "should I buy this?" advice.

Secondary audience: the ESPRIT jury, who see the app driven by the team on a laptop during the project presentation.

## Product Purpose

DressMe helps people get more out of the clothes they own and buy second-hand with fewer regrets:
- digitise the wardrobe by photographing items (the models fill in category, type, pattern and colour; the user confirms or corrects);
- answer "should I buy this?" in the friperie from one photo, against what they already own;
- suggest, score and complete outfits from their own wardrobe, filtered by modesty level, season and occasion;
- find look-alikes ("you already own something like this") and inspiration;
- chat with an assistant that only talks about clothes they really own.

Success: a user scans an item in a friperie and gets a clear buy / think / skip answer in seconds, and plans outfits without buying duplicates.

## Positioning

Built for the friperie reality: a single photo of an unlabelled second-hand item is judged against the user's own wardrobe (how many good new outfits it makes, near-duplicates already owned), within their modesty preference and budget mindset. The advice is explained ("two bold patterns", "you already own 1 very similar top"), not a black box.

## Operating Context

- In the friperie: phone in one hand, between racks, varied light, patchy mobile data; decide in seconds.
- At home: phone; photographing clothes to build the wardrobe, planning tomorrow's outfit, chatting with the assistant.
- Jury demo: laptop on a big screen, driven by the team.
- The models (classifier, colour, FashionCLIP) run on the team's backend; uploads take a moment to analyse.

## Capabilities and Constraints

- Backend endpoints: register / login (JWT), profile (name, `min_coverage` 1-5 modesty level, language), wardrobe CRUD with photo upload and per-field corrections, `/analyze` (photo not saved, candidate kept 24 h), `/buy-advice` (buy / think / skip, good outfits count, reasons, best outfits), `/outfits/score|suggest|complete`, `/similar` (wardrobe + dataset catalog), `/chat` (Gemini with tools; 503 when no API key is configured).
- Every model answer carries a confidence. Colour on phone photos is often below the 0.7 cut and arrives empty with a guess in `predicted`: confirming colour must be quick.
- Schema vocabularies are fixed: 9 categories (top, bottom, dress, outerwear, shoes, bag, accessory, traditional, swimwear), sub_categories from `mappings/sub_category_vocabulary.csv`, 5 patterns, 21 palette colours, seasons (summer, winter, mid-season), occasions (casual, formal, sport, wedding, eid, work), coverage 1-5.
- Languages: English by default; French and Arabic available; Arabic requires a right-to-left layout.
- Dataset catalog images are for the academic demo only: shown to logged-in users, never published or used in marketing.
- Mobile-first, but must also present well on a laptop screen.

## Brand Commitments

Name: DressMe. No logo, colours or voice decided yet (decided 2026-10-03: start fresh).

## Evidence on Hand

- Survey figures above (57 responses); personas named in Phase 1 (details in the team's Phase 1 documents, not in this repo).
- No real user testimonials, ratings, users or partner friperies exist: never fabricate them.
- Model accuracy figures are in `reports/phase4/*_evaluation.md` (e.g. classifier 95.7% category on test).

## Product Principles

1. Decide in seconds: the friperie verdict is the hero moment; everything else supports it.
2. The user is the authority: every predicted field is visible, explained by its confidence, and correctable in one tap.
3. Their wardrobe, not a catalog: advice is grounded in what they own; re-using clothes beats buying more.
4. Respect modesty and budget: preferences filter suggestions silently and never get pushed against.
5. Explain, don't judge: reasons in plain words, kind tone.

## Accessibility & Inclusion

- Right-to-left support for Arabic (mirrored layout, correct text direction, bidi-safe numbers).
- Readable in variable light (friperie): strong contrast; one-handed use on phones (primary actions within thumb reach).
- Modesty levels are a respected preference, never framed as a restriction or a joke.
