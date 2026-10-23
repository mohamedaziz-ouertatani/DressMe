# Manual check: step 2 and 2b, the Dress page

You need the app running (`docker compose up`, then http://localhost:5173). Use the demo account
`demo@example.com` (17 pieces) for A to H, and brand-new accounts for I to K. Tick each line. "OK" means what
is written; anything else is a bug to report with the line number.

## A. For today: the page and each chip

1. Sign in. OK: you land on **Dress** (address `/dress`), the switch shows **For today** selected, a line
   "Everyday · today · 22° and clear" (your weather), the big title **Three outfits**, the chips **Everyday**,
   **Work**, **University**, **Outing**, **More**.
2. OK: three cards, tinted soft green (Safe), yellow (Bolder) and lilac (Experimental), or fewer / other
   labels if your wardrobe gives them: each card has its label as its title, five dots and a word
   (high ●●●●●, medium ●●●○○, low ●○○○○), a collage of photos (main pieces large, shoes / bag small), two
   short reasons ("The pieces share one style", "Right for everyday at 22°"), a black **Wear this** and a ✦ button.
3. Tap each chip: **Work**, **University**, **Outing**, then **More** (it reveals **Eid**, **Wedding**,
   **Beach**) and each of those. OK: the context line names the chip, the cards change, the chip you tapped is
   filled black.
4. On **Beach**: OK: outfits around a swimsuit, with no shoes; with no swimsuit in the wardrobe, a message that
   there is none yet.
5. Choose **Outing**, reload the page. OK: **Outing** is still selected (remembered).

## B. Reopening and New outfits

6. Note the three outfits (which pieces). Reload, or close the tab and open Dress again. OK: the same three
   outfits (same day, same chip).
7. Tap **New outfits**. OK: after a moment the outfits are different (they may share a piece), the title and
   chips stay. Tap it again: different again. Switch the chip and back: the first outfits of that chip.

## C. The details sheet

8. Tap ✦ on a card. OK: a sheet rises over everything, **including the bottom tab bar**. It shows: **Score**
   (for example 83 / 100) with the points per part; **Why this confidence** (a sentence per reason, or "Nothing
   lowers it."); the weakest piece and its swap, and how each pair works; **All the reasons**; **Try it on**
   and a thumbs up / down.
9. Tap the thumbs up. OK: it stays pressed. Press Escape, or the X, or the dark area. OK: the sheet closes and
   the page behind scrolls again. Tap **Try it on**. OK: the try-on page opens with the pieces.

## D. Wear this and Undo

10. Tap **Wear this** on a card. OK: a spinner, then **Worn today** with an **Undo** link.
11. Reload. OK: the same card still says **Worn today · Undo**. (In `http://localhost:8000/docs`, `GET /wear`
    lists one entry: `source: "card"`, today's date in Tunis, `label_shown`, `score_shown`.)
12. Tap **Undo**. OK: **Wear this** is back; `GET /wear` no longer lists it.
13. Stop the backend (`docker stop dressme-backend-1`), tap **Wear this**. OK: a message about no connection with
    **Try again**. Start it again (`docker start dressme-backend-1`, wait until healthy), tap **Try again**. OK:
    **Worn today**.

## E. Build

14. Tap **Build** in the switch. OK: the address is `/dress/build`; the title **Build**, a hint, "Selected: 0",
    your pieces grouped by category, and a black **Build outfits (0)** button, disabled, above the tab bar.
15. Tap one top. OK: it turns black, "Selected: 1", the button reads **Build outfits (1)**. Tap **Build outfits (1)**.
    OK: the page scrolls to up to three cards, each containing your top, in the same card design; no "Your pick"
    (one piece does not make an outfit).
16. Tap **New outfits**. OK: other completions around the same top.
17. Add a bottom and shoes (three pieces: a top, a bottom, shoes), tap **Build outfits (3)**. OK: the first card is
    marked **Your pick** and holds exactly your three pieces (plus nothing you did not choose); the others
    follow.
18. A clash: pick two tops (for example a shirt, then a t-shirt), tap Build. OK: a short note "The T-shirt replaced
    the Shirt: an outfit has one piece of each kind.", the selection now shows only the T-shirt.
19. **Wear this** on a Build card. OK: **Worn today · Undo**; `GET /wear` shows `source: "build"`.

## F. The old addresses

20. Open http://localhost:5173/today. OK: it becomes `/dress`. Open `/build`. OK: it becomes `/dress/build`
    (Build selected). Open `/`. OK: `/dress`.
21. OK: the menu has **Dress**, **Wardrobe**, **Worth it?**, **Shops**, **Assistant** (no Today, no Build); on a
    phone width the bar shows **Dress**, **Wardrobe**, the big **Buy?**, **Shops**, **Assistant**, and the header
    no longer has a Shops icon.

## G. Arabic, right to left

22. Profile > language **العربية**. Walk through 1, 2, 8, 10 and 15. OK: the page is right to left; the switch
    reads **لليوم** | **نسّق**; the title **ثلاث لبسات**; the chips **يومي**, **عمل**, **جامعة**, **نزهة**, **المزيد**
    (then **عيد**, **عرس**, **بحر**); the cards read **آمنة** / **أجرأ** / **تجريبية**, the button **سأرتديها**, then
    **ارتديتها اليوم** and **تراجع**; the dots and the ✦ button swap sides; no English text is left except
    "DressMe" and the place name.
23. Switch to French. OK: **Pour aujourd'hui** | **Composer**, **Trois tenues**, **Sûre** / **Plus audacieuse** /
    **Expérimentale**, **La porter**, **Portée aujourd'hui**, **Annuler**, **Nouvelles tenues**, nav **Tenue**.

## H. 390 px width

24. Browser dev tools, device toolbar, width **390**. On For today, on Build (with results), with the sheet open and on
    the empty page: OK: no horizontal scrollbar; the chips wrap onto two lines; the collage never overflows the
    card; the last card and **New outfits** scroll fully above the bottom tab bar; the sticky **Build outfits (n)**
    button sits just above the tab bar and never covers a piece you can still tap when scrolled to the end.
25. Repeat 24 in Arabic and at 1280 px (three cards side by side, the sidebar items each on one line).

## I. An empty wardrobe

26. Sign out, create a new account (any email, gender women), open **Dress**. OK: instead of cards, a card
    "Your first outfit is three photos away" listing what is missing ("Add a top and a bottom, or a dress, to
    start building outfits." ...) and a black **Add pieces** button that opens the wardrobe. Tap **Build**. OK: the
    empty-wardrobe message and the same button.
27. Add one top. Back on **Dress**. OK: "You have tops but no bottom: one bottom unlocks your first outfits." and the shoes line.

## J. A wardrobe without a taste vector

28. With the same account, add a bottom and shoes (three pieces in all, so there are outfits) and remove one so only
    two pieces carry a picture vector (or use any account with fewer than 3 pieces that can still make an
    outfit). OK: the cards are grey, titled **Outfit 1**, **Outfit 2**, **Outfit 3** (no label name), and above
    them the hint "Add a few more pieces so we learn your style." After adding a third piece the labels and
    tints appear.
29. OK on this small wardrobe: the dots read low or medium and the sheet's **Why this confidence** says "You only
    have N usable pieces: DressMe needs about 8 to judge well."

## K. The recent-wear penalty (optional, off by default)

30. Mark today's first outfit as worn. In `mappings/dress_rules.csv` set `wear_penalty_days` to `3` and
    `wear_penalty_points` to `20` (no restart: read at each call). Open `GET /outfits/suggest?n=5` in `/docs`:
    OK: the outfit worn today is no longer first (scores unchanged). Put both values back to `0`: the first
    outfit is back.

## L. Step 2c: friendly errors and relative labels

31. With the app open on **Dress** (For today), stop the backend (`docker stop dressme-backend-1`) and tap
    **New outfits**, or reload. OK: a short sentence ("No connection..." when offline, else "Couldn't load outfits")
    and a **Try again** button; no "Not Found", no JSON. The details are only in the browser console. Start the backend
    (`docker start dressme-backend-1`, wait until healthy), tap **Try again**: the cards come back. Repeat in
    **Build** (pick a piece, **Build outfits**: "Couldn't build outfits") and in French and Arabic.
32. After any backend change run `docker compose up -d --build backend` and wait about a minute.
33. On the demo account (17 pieces), For today and Build with 3 cards: OK: the labels are **Safe**, **Bolder** and
    **Experimental**, one each (tints green, yellow, lilac). With fewer than 3 cards the labels follow the old
    cuts (`dress_rules.csv`).
