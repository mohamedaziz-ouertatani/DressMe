# Manual check: step 2, Dress (labels, "I wore this")

You need the app running (`docker compose up`, then http://localhost:5173). Use the demo account
`demo@example.com` (17 pieces) for A to F, and a second, brand-new account for G. Tick each line. "OK" means
what is written; anything else is a bug to report with the line number.

## A. Today with labels and confidence

1. Sign in and open **Today**. OK: an outfit card with a small chip above the pieces: **Safe**, **Bolder** or
   **Experimental** (with a small icon), on the side opposite the round score stamp, not touching it.
2. Tap **Another one** a few times. OK: most outfits of the demo wardrobe are **Safe**; the chip changes with
   the outfit; no outfit shows a chip it should not have (a brand-new account with fewer than 3 pieces shows
   no chip at all: see G).
3. OK: no "Confidence: low" badge on the demo account (17 pieces). It appears in G.
4. Change the Season and Occasion chips. OK: the outfits and chips update, the list order is the one the app
   always gave.

## B. I wore this, then Undo

5. On an outfit card tap **I wore this**. OK: the button shows a spinner for a moment, then the line
   **Worn today** with an **Undo** link in its place.
6. Tap **Undo**. OK: **I wore this** is back. (Check in http://localhost:8000/docs, `GET /wear`, that the
   entry is gone.)
7. Tap **I wore this** again, then open `GET /wear` in `/docs`. OK: one entry, `source: "card"`,
   `worn_on` = today's date in Tunis, `score_shown` = the stamp's number, `label_shown` = the chip.

## C. I wore this, then a reload

8. With the outfit marked as worn, reload the page (F5). OK: after a moment the same outfit still shows
   **Worn today · Undo** (not "I wore this"). Other outfits (tap **Another one**) show **I wore this**.
9. Two tabs: open **Today** in tab 1 and tab 2 on the same outfit (before marking it). Tap **I wore this** in
   tab 1, then in tab 2 (which still says "I wore this"). OK: tab 2 shows **Worn today · Undo** and
   `GET /wear` still lists one entry for those pieces that day (no duplicate).
10. Stop the backend (`docker stop dressme-backend-1`), tap **I wore this** on a not-yet-worn outfit. OK: a
    message about no connection with **Try again**, the button stays usable. Start it again
    (`docker start dressme-backend-1`, wait until healthy), tap **Try again**. OK: it becomes **Worn today**.

## D. Build with labels

11. Open **Build**, pick 3 pieces (a top, a bottom, shoes). OK: the outfit shows the score stamp, a chip
    (Safe / Bolder / Experimental) and **I wore this**; picking another piece updates the chip.
12. Tap **I wore this** on Build. OK: **Worn today · Undo**; in `GET /wear` the entry has
    `source: "build"`.

## E. Empty or too small wardrobe: what is missing

13. Sign out, create a new account (any email, gender women), open **Today**. OK: the card "Your first outfit
    is three photos away" lists what is missing, for example "Add a top and a bottom, or a dress, to start
    building outfits." (and no shoes), with an **Add pieces** button that opens the wardrobe.
14. In the wardrobe add one top (a photo). Back on **Today**. OK: the message becomes "You have tops but no
    bottom: one bottom unlocks your first outfits." and the shoes line.

## F. Arabic, right to left

15. Profile > language **العربية**. Walk through 1, 5, 8, 11 and 13 again. OK: the page is right to left; the
    chip and the badge sit at the right, the stamp at the left, not touching; the words are **آمنة** /
    **أجرأ** / **تجريبية**, **ارتديتها**, **ارتديتها اليوم**, **تراجع**; no English text is left (except the
    place name and "DressMe").
16. Switch to French. OK: **Sûre** / **Plus audacieuse** / **Expérimentale**, **Je l'ai portée**,
    **Portée aujourd'hui**, **Annuler**.

## G. Low confidence (small wardrobe)

17. With the new account of 13-14, add three pieces: a top, a bottom and shoes. Open **Today**. OK: an outfit
    shows, with a dashed **Confidence: low** badge (fewer than 8 pieces) and, because there are 3 pieces
    with a picture, a label chip.
18. With only 2 pieces (delete one, then open **Build** and pick both). OK: no label chip (no taste vector
    yet), the low-confidence badge is shown.

## H. 390 px width

19. Browser dev tools, device toolbar, width **390**. On **Today** (with a chip and the low badge), on
    **Build**, and on the empty **Today**: OK: no horizontal scrollbar; the chip row wraps instead of
    running under the stamp; **I wore this** is a full-height button; the last element scrolls fully above
    the bottom tab bar.
20. Repeat 19 in Arabic.

## I. The recent-wear penalty (optional, off by default)

21. Mark today's first outfit as worn. Open `mappings/dress_rules.csv`, set `wear_penalty_days` to `3` and
    `wear_penalty_points` to `20` (no restart: the file is read at each call). Reload **Today**. OK: the
    outfit worn today is no longer the first one (the scores shown did not change). Put both values back to
    `0` and reload. OK: the first outfit is back.
