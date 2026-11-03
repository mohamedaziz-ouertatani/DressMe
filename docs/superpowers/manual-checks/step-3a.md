# Manual check: step 3a, the old chat is removed

The backend changed (the chat routes and `google-genai` are gone), so rebuild it first:
`docker compose up -d --build backend`, then wait about a minute. Then open http://localhost:5173 with your own
account. Check at phone width (browser dev tools, device toolbar, **390 px**) unless a line says otherwise. Tick each
line; anything else is a bug to report with the line number.

## A. The Assistant placeholder

1. The phone tab bar has five items: Home, Dress, Buy?, Wardrobe, **Assistant** (a speech bubble). Tap **Assistant**. OK:
   the address is `/assistant`, the tab shows its name on the black pill, and the page has a small line **Coming back
   soon**, the headline **Assistant**, and a white card with a speech-bubble icon on a blue disc, **The assistant is
   being rebuilt**, one sentence ("A new assistant is on its way. Everything else in DressMe works as usual.") and a
   black button **See today's outfits**.
2. Scroll to the bottom. OK: nothing scrolls sideways, and the button is fully above the tab bar (also at **360 x 640**).
3. Tap **See today's outfits**. OK: it opens **Dress**.
4. On a wide window (1280 px), open the same page from the left rail (**Assistant**). OK: the same card, no tab bar.
5. Profile > language **Français**. OK: **Bientôt de retour**, **Assistant**, **L'assistant est en cours de
   reconstruction**, the sentence and **Voir les tenues du jour**.
6. Profile > language **العربية**. OK: the page mirrors right to left, the kicker is **يعود قريبا**, the headline
   **المساعد**, the card **يجري إعادة بناء المساعد**, and the button **عرض إطلالات اليوم**. Nothing is cut off. Switch back
   to English.

## B. The old addresses and links

7. Type `http://localhost:5173/chat` in the address bar. OK: it ends on `/assistant` (the placeholder).
8. On **Home**, tap the lilac row **Ask the stylist** ("Outfit ideas in plain words"). OK: it opens `/assistant`.
9. Look for any other way to the old chat page (Wardrobe, Profile, the Wardrobe view, an item page). OK: there is none.

## C. Admin

Log in as an admin (or `docker compose exec backend python -m app.make_admin you@example.com`, log in again) and open
`/admin`.

10. **Overview** loads with no error. OK: the left list (Accounts, Active, Wardrobe items, Uploads, Scans, Verdicts,
    Corrections, Try-ons) has **no "Chat messages" line**.
11. Open **Show as a table** under "Activity per day". OK: if your database still holds events of the old chat, those
    days have an extra column **Old chat** and the chart's day details say "old chat messages N"; with no old events
    there is no such column.
12. Open **Explainability**. OK: it loads with **Real use: the flag on uploads** and the **XAI settings**; there is **no
    "Chat: what the agents' tools did"** section. Change nothing.

## D. The API and the database

13. Open http://localhost:8000/docs. OK: no `/chat` and no `/chat/history`; every other route is still listed
    (67 operations; there were 70).
14. In PowerShell: `curl.exe -s -o NUL -w "%{http_code}" -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{}"`.
    OK: `404`.
15. `docker exec dressme-mongo-1 mongosh dressme --quiet --eval "db.getCollectionNames()"`. OK: the list has **no `chats`**;
    `events` is still there.
16. Without Ollama running (quit it from the tray): `docker compose up` still works, and
    `powershell -ExecutionPolicy Bypass -File scripts\check_demo.ps1` ends with `RESULT: PASS` and has no Ollama line.

## E. A quick tour (nothing else should have changed)

17. **Home**: the greeting, the weather line, Today's pick, the tiles. **Dress**: For today shows outfits; **Build** scores
    two pieces. **Buy?**: scan a photo, get the verdict, **Bought it** or **Left it** works. **Shops**: the list loads.
    **Wardrobe view** (`/insights`): the four sections load. **Wardrobe**: open an item, **Why these labels?** opens.
18. Delete a test account from Profile (**Delete my account**) and check you are sent to the welcome page.

## F. The old code is still readable

19. `git show pre-chat-removal:backend/app/chat_engine.py | more`. OK: the old file's first lines (the Gemini / Ollama
    docstring). `git tag` lists `pre-chat-removal`.
