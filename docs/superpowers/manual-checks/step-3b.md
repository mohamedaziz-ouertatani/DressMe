# Manual check: step 3b, search your wardrobe (words or a photo)

The backend changed (the new route `POST /search`), so rebuild it first: `docker compose up -d --build backend`, wait about a
minute. Then open http://localhost:5173 with your own account and **some pieces in the wardrobe (8 or more is best)**.
Check at phone width (browser dev tools, device toolbar, **390 px**) unless a line says otherwise. Tick each line; anything
else is a bug to report with the line number. Numbers are never shown by the search: only the words below.

## A. The bar

1. Open **Wardrobe**. OK: under the title there is a rounded field with a magnifier and the grey hint **Search, e.g. "black
   jeans"**, a round **camera** button and a round black **magnifier** button, all on one line. The "N pieces" bar, the
   category chips and the grid are below, as before.
2. Tap a piece in the grid. OK: its page opens (no change from before).

## B. Five searches (do them in English first)

3. **Words, English.** Type the name of something you own, for example `black jeans` or `pink top`, and press Enter. OK:
   "Looking through your wardrobe…" with grey blocks, then a grid. The piece you meant is **first**, with a green
   **Close match** badge; the other pieces below it are **faded** (they are only the nearest, not matches). A **Clear search**
   link sits above the grid, and the upload bar and the category chips are hidden while the results show.
4. **Words, French.** Switch the app to **Français** (Profile). Type `pantalon noir` (or any French name of a piece you own:
   `haut rose`, `robe`, `chaussures`). OK: the same kind of answer; the badge says **Très proche**.
5. **Words, Arabic.** Switch to **العربية**. Type `جينز أسود` (or `فستان`, `حذاء`, `حقيبة`). OK: the page is right to left,
   the answer is the same kind, the badge says **تطابق قريب**, nothing is cut off. (Darija words are not understood yet.)
6. **A photo.** Tap the **camera** button (on a computer it opens a file picker; on a phone, the camera). Pick a photo of one
   piece (best: one of your own pieces on a plain surface). OK: the grey blocks, then the results with a small copy of your
   photo above them; a piece that looks like yours is first and marked **Close match**. **Nothing is added**: go back to the
   Wardrobe and check that the number of pieces did not change and that no new piece appeared.
7. **A nonsense or missing thing.** Type `zxqv` or the name of something you do **not** own (for example `wedding dress` when
   you have none). OK: a white card with **Nothing close in your wardrobe** and "Try other words, or another photo.", then
   **Closest anyway** with up to three faded pieces. No piece carries the green badge.

## C. Around the search

8. **Clear search.** OK: the upload bar, chips and the full grid come back, and the box is empty.
9. Tap a result (also a faded one). OK: the piece's page opens.
10. Search for an empty-looking text (only spaces). OK: nothing happens.
11. Switch your phone or the browser to offline and search. OK: the grey blocks stop and a note says you are offline (with Try
    again), not a blank page. Switch back online and press **Try again**.
12. Take a photo that is not a picture (rename a text file to `x.jpg`, if your browser lets you). OK: the note **This photo
    could not be read. Try another one.**

## D. The other places and screens

13. Open **Assistant** (the tab bar's speech bubble). OK: the "The assistant is being rebuilt" card and **under it the same
    search box**; search for `black jeans`: the results appear under the box, and nothing scrolls sideways. The last card is
    fully above the tab bar.
14. Check **360 x 640** and a wide window (1280 px): no horizontal scroll, the three buttons stay on the line with the field.
15. In **العربية** the order of the three controls is mirrored (black magnifier on the left, field on the right).

## E. Privacy and the log (for the team)

16. Search for a word on purpose, such as `my secret words`. In Admin > Overview the day's activity may count it as a
    search, but **no page and no collection holds the words**: in MongoDB, `db.events.find({type: "search"})` shows only
    `mode`, `results`, `nothing_close` and `ms`.
17. Log in as a second account with no pieces and search. OK: "Nothing close in your wardrobe" and no pieces at all (never
    the first account's).
