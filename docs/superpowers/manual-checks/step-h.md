# Manual check: step H, Home and the light polish

Frontend only: no rebuild of the backend is needed. You need the app running (`docker compose up`, then
http://localhost:5173) and your own account with some pieces. Tick each line; anything else is a bug to report with
the line number. Check at phone width (browser dev tools, device toolbar, **390 px**) unless a line says otherwise.

## A. Home

1. Sign in. OK: you land on **Home** (address `/`); `/home` also opens it. At the top: today's date in your language
   (and "21° and clear" style weather when the weather is known), **Hello, <your name>**, and a round black button with
   your initial.
2. **Today's pick**: a green card with "Today's pick", the label and confidence ("Safe · Confidence: high"), the photos
   of one outfit, one reason and a round arrow. Open **Dress** (For today) in another tab: OK: the **Safe** card there
   holds the same pieces (if no card is Safe, the first card). Tap the green card: OK: Dress opens.
3. The two tiles: **Should I buy this?** opens Buy?; **Add clothes** ("One piece per photo") opens Wardrobe, where the
   photo buttons are at the top.
4. **Ask the stylist** opens the Assistant; **Shops** opens Shops.
5. **Your wardrobe · N pieces**: your newest pieces first (up to 10), swipe sideways; tap one: its item page opens.
   **See all** opens Wardrobe.
6. The peach **Gap in your wardrobe** card shows only if the Wardrobe view's "What to add next" lists something; its
   title names the first missing kind ("You have no shoes yet"); **Check a piece** opens Buy?.
7. Tap your initial: OK: the Wardrobe view opens scrolled to **Profile** (budget, consent date, delete my account).
8. A brand-new account (no pieces): OK: instead of Today's pick, a **Start here / Add your first clothes** card with an
   **Add clothes** button; no wardrobe strip and no gap card.
9. Stop the backend (`docker stop dressme-backend-1`), reload Home. OK: the header stays; Today's pick, the strip and the
   gap each show a short message with **Try again** (never "Not Found" or JSON); the tiles and rows still work. Start it
   again (`docker start dressme-backend-1`, wait until healthy), tap each **Try again**.

## B. The tab bar

10. At 390 px: a white floating pill at the bottom with **Home, Dress, Buy?, Wardrobe, Assistant** (Shops is no longer in
    it). The current tab is black with its icon and name; the others show only an icon. Tap each: the right page opens.
11. Scroll every page to the very bottom: OK: the last button or card is fully above the floating bar.
12. Arabic (Profile > language **العربية**): OK: the bar reads right to left (Home on the right), Home's collage, tiles and
    strip mirror, the arrow points left, and the Arabic headlines use the same Arabic font as before.
13. At 1280 px: the side rail starts with **Home**, then Dress, Wardrobe, Worth it?, Shops, Assistant.

## C. The polished pages still work

14. **Wardrobe**: add a piece (Take a photo / Choose from gallery): OK: it is analysed and its page opens; the filter chips
    still filter. The item page: correct a label, it saves.
15. **Buy?**: scan a piece. OK: the verdict is a coloured pill with a word and an icon (green **Buy**, amber **Think**,
    red **Skip**), the confidence pill, the reasons, the best outfits, **Bought it / Left it** work as before.
16. **Shops**: the chips filter, a listing opens, **Should I buy this?** gives the same verdict card.
17. **Wardrobe view**: Worn, Bought and left, Wardrobe stats and Profile load; saving a budget still works.
18. **Login / sign-up**: the fields, the consent checkbox and the errors work as before; a wrong password shows a red message.
19. Not changed on purpose: the **Admin** pages and the **Assistant** page keep the old ticket look.
