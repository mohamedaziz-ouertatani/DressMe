# Manual check: step H2, the Buy? page in the Dress look

Frontend only: no rebuild of the backend is needed. You need the app running (`docker compose up`, then
http://localhost:5173) and your own account with some pieces (8 or more, so that one check below is not "low"
confidence). Tick each line; anything else is a bug to report with the line number. Check at phone width (browser dev
tools, device toolbar, **390 px**) unless a line says otherwise.

## A. The start screen

1. Open **Buy?**. OK: the headline **Should I buy this?**, one sentence, a black frame with four white corner marks and
   **Fit one item inside the frame**, then **Price (TND)** ("Optional: the price on the tag."), **Take a photo**,
   **Choose from gallery**, and the two links to Shops and Sell. The tab bar is at the bottom.
2. Type `abc` in the price. OK: a red "Enter a price above 0, or leave it empty."; clear it again.
3. Choose a photo of one piece **without a price**. OK: the photo appears in the frame and a white line sweeps down it
   while "Reading the photo…" shows under it. With "reduce motion" switched on in the system, the line stands still.
4. OK: a white card with the piece's name **in the app's language only** (no Arabic under the English name), **Check
   what DressMe saw** and its fields; **Why these labels?** opens and closes. Correct a field if you like.

## B. The verdict

5. Tap **Get the verdict**. OK: the screen changes to the verdict, scrolled to the top: a round back button and the piece's
   name; **the tab bar is gone** and a bar with **Bought it** (black) and **Left it** (outlined) sits at the bottom.
6. The white card: the piece on a grey tile, the verdict as a coloured pill with a word and an icon (green **Buy**, amber
   **Think** or red **Skip**), a big number = how many good outfits it makes, and under it "good outfits · no price
   given".
7. The three bars: **Good outfits**, **"Buy" needs**, **"Think" needs**, each with its whole number at the end. Open **Why
   this verdict?**: OK: the same three numbers are in its first sentence.
8. Under a hairline: the confidence as five dots and a word (the same dots as on Dress).
9. **Why**: one row per reason, each with a round **+** (green, in favour) or **−** (red, against). The first row says
   how many good outfits it adds; when it adds some, up to three small photos of your pieces from those outfits sit at
   its end. A "you already own a very similar piece" row shows that piece's photo.
10. **Similar pieces** and **Try it on** open their pages; come back with the browser's back button and scan again.
11. **Best outfits with it**: up to two cards like the Dress cards (white, the pieces on grey tiles, "Score NN / 100");
    an outfit without a top and a bottom shows the amber **Incomplete** note. No stamps, no "01/03" stubs, no "№" serial.
12. Scroll to the very bottom. OK: the last card is fully above the Bought it / Left it bar.
13. Tap the round back button. OK: the start screen again, with the tab bar back.

## C. With a price, and low confidence

14. Scan the piece again **with a price** (e.g. `45`). OK: under the number, "good outfits · 45 TND". With a budget set on
    the Wardrobe view and a price above it, a row "At … TND it takes …% of your budget." appears in **Why**.
15. With a small wardrobe (fewer than 8 pieces, e.g. a new account) or a piece whose labels were guessed: OK: the dots show
    **low**, and an amber banner **Less certain than usual** with one sentence (e.g. "Your wardrobe is still small…")
    sits under the card. With high or medium confidence there is no banner.

## D. Bought it / Left it

16. Tap **Left it**. OK: the bar turns into a black check disc, **Saved**, "Recorded: you left it" and **Scan another**
    (which opens the start screen). There is no Undo: the first answer stands.
17. Scan another piece, tap **Bought it**. OK: **Saved**, "Added to your wardrobe" and **Open the item**, which opens the
    new piece (it says "Added from a scan"). The Wardrobe view's "Bought and left" lists both answers.
18. Stop the backend (`docker stop dressme-backend-1`) on a verdict, tap **Bought it**. OK: a short error with **Try
    again** above the buttons (never "Not Found" or JSON). Start it again, wait until healthy, tap **Try again**.

## E. Shops

19. Open **Shops**, a listing, **Should I buy this?**. OK: the same verdict card under the listing, with the listing's
    price under the number ("… · 89 TND"); the tab bar gives way to the Bought it / Left it bar; nothing scrolls sideways.
    **Left it**: "Saved", with no Scan another link; leave the page: the tab bar is back.

## F. Arabic and desktop

20. Profile > language **العربية**, repeat 1, 5 to 9 and 16. OK: everything reads right to left: the photo tile is on the
    right of the card and the pill on its left, the bars fill from the right, the + / − discs are on the right and the
    small photos on the left, the back arrow points right. No line scrolls sideways.
21. At 1280 px: the verdict sits in the content column and the Bought it / Left it bar stays under it at the bottom of the
    window (the side rail stays usable).
