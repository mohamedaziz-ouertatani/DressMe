# Manual check: step 1, "Should I buy this?"

You need the app running (`docker compose up`, then http://localhost:5173), signed in as a user with a
wardrobe (the demo account `demo@example.com` has 17 pieces), and 4 photos of one piece each. Tick each
line. "OK" means what is written; anything else is a bug to report with the line number.

## A. Scan, price, verdict, Bought it

1. Open **Should I buy this?** in the menu. OK: title "Should I buy this?", the tip "One piece per photo."
2. Pick a photo. OK: "Reading the photo…" with grey placeholder rows, then the photo with its name.
3. Under "Check what DressMe saw", correct one field (for example the colour). OK: it turns solid.
4. In "Price (TND)" type `abc`. OK: red message "Enter a price above 0, or leave it empty." and the verdict button is disabled.
5. Type `0`. OK: same message. Type `89,9` (comma). OK: no message, button enabled. Empty is also fine.
6. Tap **Get the verdict**. OK: "Comparing with your wardrobe…" on the button, then the card.
7. The card shows: the stamp (Buy / Think / Skip) next to "It adds N good outfits…", a **Confidence** badge,
   the reasons, a "Good to know" list if any, "Why this verdict?", "Best outfits with it", **Similar pieces**,
   **Try it on**, and **Bought it** / **Left it** at the bottom.
8. If the badge is medium or low, the reason sits right under it (for example "You only have 5 usable pieces…").
9. Tap **Bought it**. OK: the buttons go busy, then you land on the new item page.
10. On the item page. OK: the line "Added from a scan" under the photo, the same labels (including your correction) as in the scan, and the photo is the cleaned one. The piece is also in the Wardrobe list.

## B. Tapping Bought it twice

11. Scan another piece and get its verdict. Tap **Bought it** twice quickly. OK: one item only is added (check the Wardrobe), no error.
12. The "different answer" message (409) cannot be reached by clicking: each scan has one card and it locks after the first answer. It is covered by `tests/test_promote_decisions.py`. To see it by hand, scan a piece and get its verdict, then in http://localhost:8000/docs (Authorize first) call `POST /decisions` with `left` for that scan, then tap **Bought it** in the app. OK: "You already gave a different answer for this piece. The first answer stands." and both buttons disabled.

## C. Left it

13. Scan a third piece, get the verdict, tap **Left it**. OK: you return to a fresh scan page (photo picker), and nothing was added to the Wardrobe.

## D. Shop listing

14. Open **Shops**, then any piece in stock. OK: its price is shown at the top.
15. Tap **Should I buy this?**. OK: the same card as on the scan page, no price field, no "Try it on".
16. Tap **Bought it**. OK: stays on the same page; the card says "Added to your wardrobe" with **Open the item**; both buttons disabled. Tap the link: the item opens with "Added from a scan". Go back to Shops and open another piece: it starts clean.
17. On another piece, get the verdict and tap **Left it**. OK: "Recorded: you left it", buttons disabled, you can keep browsing.

## E. Expired scan

18. Scan a piece and get the verdict, but do not answer yet.
19. Find the scan's id. It is in the address of **Similar pieces** (`/similar?candidate=<ID>`), or run in PowerShell
    (the newest candidate is the piece you just scanned):
    `docker exec dressme-mongo-1 mongosh dressme --quiet --eval "db.candidates.find({}, {category:1, created_at:1}).sort({created_at:-1}).limit(3)"`
20. Delete only that one (replace `<ID>` with the 24 hex characters):
    `docker exec dressme-mongo-1 mongosh dressme --quiet --eval "db.candidates.deleteOne({_id: ObjectId('<ID>')})"`
    It must print `deletedCount: 1`. Never use `deleteMany`.
21. Tap **Bought it**. OK: message "This scan has expired (scans are kept for 24 hours)." with **Scan again**; the buttons are disabled. Tap **Scan again**: you are back to a fresh scan page.
22. Same on a Shop listing (repeat 18-20 for its candidate, then tap Bought it). OK: the same message, with **Check again** instead; tapping it brings back the "Should I buy this?" button.

## F. Network error

23. Get a verdict, then stop the backend (`docker stop dressme-backend-1`) and tap **Bought it**. OK: the message about no connection with **Try again**, buttons still usable. Start it again (`docker start dressme-backend-1`), wait until it is healthy, tap **Try again**. OK: the answer is recorded.

## G. Arabic, right to left

24. Profile > language **العربية**. OK: the page flips to right-to-left.
25. Phone tab bar: the centre button reads **أشتري؟** on one line. The page title is **نشريها؟**.
26. Walk through A (6-9) again. OK: text aligned right, arrows point left, Bought it / Left it start from the right, no text cut off or overlapping, and every text is Arabic (no English left; the stamp ring may mix scripts, as before).
27. Switch to French and look at the same screens. OK: the tab bar says **Acheter ?**, no English left.

## H. 390 px width

28. Open browser dev tools, device toolbar, width **390**. On the scan page, the card, the item page and a Shop listing: OK: no horizontal scrollbar, the stamp and the sentence fit on one row, the buttons wrap to a second line instead of overflowing, nothing hides under the bottom tab bar when you scroll to the end.
29. In English the tab bar reads **Buy?**, French **Acheter ?**, Arabic **أشتري؟**: none wraps onto two lines.
