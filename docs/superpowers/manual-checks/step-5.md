# Manual check: step 5, the Wardrobe view

You need the app running (`docker compose up`, then http://localhost:5173), and the backend rebuilt with this
code (`docker compose up -d --build backend`, wait about a minute). Use the demo account `demo@example.com`
for A to E and G. **Never delete the demo account** (the app refuses it anyway).

**For F, please create a throwaway account first** (any email such as `throwaway@example.com`, any password of
8+ characters), and add one piece to it. Only that account is deleted.

Tick each line. "OK" means what is written; anything else is a bug to report with the line number.

## A. The page

1. Sign in, open **Wardrobe**, tap the link at the top (it now says **Wardrobe view**). OK: the address is
   `/insights`, the title **Wardrobe view**, the sections in this order: **Worn**, **Bought and left**,
   **Wardrobe stats**, **Profile**. There is no "To check" section. No new item in the menu or the phone tab bar.
2. OK at 390 px width (browser dev tools, device toolbar): no horizontal scrollbar, the last section scrolls fully
   above the tab bar.
3. Language **Français** and **العربية** (Profile page, or the switch on the sign-in page): OK: the title reads
   **Vue de la garde-robe** / **نظرة على الخزانة**, every sentence of the page is translated, Arabic is right to left.

## B. Worn

4. Open **Dress**, tap **Wear this** on an outfit. Back on the Wardrobe view. OK: under **Worn in the last 14 days**
   each piece of that outfit appears with "Last worn <today>", and **History** lists today's date with the
   pieces' photos. Tap a photo: OK: the piece's page opens.
5. OK: **Never worn** lists the pieces you never wore, only if they were added more than 14 days ago (on a
   freshly seeded demo account that may be none: the line "Everything you have had for a while has been worn" is
   fine). With nothing worn at all, **Worn in the last 14 days** says to tap "Wear this" on the Dress page.
6. Back on Dress, **Undo** the outfit. OK: on the Wardrobe view (reload) the pieces left **Worn lately**.

## C. Bought and left

7. In **Worth it?** scan a photo, tap **Bought it**; scan another, tap **Left it**. OK: **Bought and left** lists
   both, each with the Bought / Left tag, the verdict the app gave **at the time** ("Verdict then: Buy · high
   confidence"), and the date. The bought one links to its piece. With no decision yet: the sentence
   explaining how to make one.

## D. Budget

8. Under **Profile** type `150` in **Budget (TND)**, tap **Save**. OK: "Saved", a **Remove budget** button appears.
   Reload: **150** is still there. Type `0` and Save: OK: "Enter an amount above 0." and nothing is saved.
9. Scan a piece and enter a tag price that is a large part of the budget. OK: the verdict can mention the budget
   (the over-budget note of step 1; the cut is in `mappings/verdict_rules.csv`). Tap **Remove budget**. OK: the field empties.

## E. Consent

10. Under **Profile**: OK: "You agreed on <date>." for an account that agreed, or "No consent date saved." for an
    account from before the checkbox.
11. **An existing account without a date** (every account created before this step; in MongoDB `consent_at` is
    missing): sign in. OK: a full-page dialog **Before you start** with **I agree** and **Log out**, nothing
    else; Escape and reloading keep it. Tap **I agree**: the app opens, and the Profile shows the date. Sign in
    again: the dialog does not come back.
12. Choose **Log out** on the dialog instead (with another such account): OK: you are on the welcome page and the
    date was not saved.
13. **Sign-up**: open the sign-up page. OK: a checkbox "I agree that DressMe keeps my photos and wardrobe to advise
    me." Submit without ticking: the browser or the page refuses ("Tick the box to create your account."). Tick it
    and sign up: OK: you land on Dress with no consent dialog, and the Profile shows today's date.

## F. Delete my account (the throwaway account only)

14. Sign in with the **throwaway** account. Wardrobe view > Profile > **Delete my account**. OK: a sheet with the
    title **Delete your account?**, a clear warning (account, photos, wardrobe, wear history, decisions, cannot be
    undone), a password field, **Delete everything** and **Close**. **Close** closes it and nothing happens.
15. Type a **wrong** password, tap **Delete everything**. OK: the message "Wrong password." under the field, you
    stay signed in, nothing was deleted (the Wardrobe still shows your piece).
16. Type the right password, tap **Delete everything**. OK: you are signed out and on the login page.
17. Try to sign in again with the same email and password. OK: "Wrong email or password".
18. (Optional) In the demo account, open Wardrobe view > Profile. OK: no delete button, a note that the demo
    account cannot be deleted.

## G. Errors

19. Stop the backend (`docker stop dressme-backend-1`), reload the Wardrobe view. OK: each section shows a
    short translated message (offline) or "Couldn't load ..." with **Try again**, never "Not Found" or JSON.
    Start it again (`docker start dressme-backend-1`, wait until healthy), tap **Try again**: the sections load.
