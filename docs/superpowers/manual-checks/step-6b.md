# Manual check: step 6b, the "Incomplete" note

You need the app running (`docker compose up`, then http://localhost:5173) and the backend rebuilt with this code
(`docker compose up -d --build backend`, wait about a minute). The note appears next to the score of an outfit that
has no top + bottom (and no dress). The score itself is unchanged, and shoes are not required.

**Build completes a pick for you**, so with a normal wardrobe a top + shoes pick gets a bottom added and shows no note.
To see the note, use a **throwaway account** (any email, any password of 8+ characters, gender women) and add only
a top and a pair of shoes (no bottom, no dress).

## A. Build, a top and shoes only

1. Sign in with the throwaway account, open **Dress**, tap **Build**, pick the top and the shoes, tap **Build outfits (2)**.
   OK: a card with those two pieces (there is nothing to complete them with) and, under the photos, the note
   **△ Incomplete: add a bottom**. Tap ✦: OK: the same note sits right under the score (the score stays visible, a number
   such as 86 / 100).
2. Switch the language to **Français** and **العربية** (Profile page). OK: **△ Incomplète : ajoute un bas** and
   **△ ناقصة: أضف قطعة سفلية** (right to left in Arabic), on one or two lines, no horizontal scrollbar at 390 px.
3. Add a bottom to the throwaway account, pick the same top and shoes in Build again. OK: the cards now hold a bottom
   and show **no note**.

## B. A top and a bottom, no note

4. In Build pick a top and a bottom (no shoes) and build. OK: the cards show no "Incomplete" note (shoes are not required).
5. For today (Dress, For today): OK: no card has a note (the suggestions always have a top + bottom or a dress).

## C. Other cases (optional, the API)

6. In `http://localhost:8000/docs`, authorize, `POST /outfits/score` with only a top's id: OK: `"complete": false,
   "missing": "bottom"`; only a bottom: `"missing": "top"`; only shoes: `"missing": "core"`; a dress alone, or top + bottom:
   `"complete": true, "missing": null`. The `score` is the same as before the step.
