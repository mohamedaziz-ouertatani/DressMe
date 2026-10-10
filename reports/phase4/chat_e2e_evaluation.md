# Chat models end to end

Whole chats through the app's engine and the agents' real tools, with no help (see `src/phase4/evaluate_chat_e2e.py`). A chat is right when the model calls exactly the reference tools in order, no tool answers an error and the answer is not empty. 8 chats per scenario (fewer when a wardrobe cannot make it), the same chats for every model, temperature 0.3 (a rerun can differ by a chat or two).

| Scenario | dressme-chat-v3 | dressme-chat-v4 |
|---|---|---|
| why_similar | 6 / 8 | 7 / 8 |
| similar | 6 / 8 | 6 / 8 |
| search | 8 / 8 | 8 / 8 |
| buy | 6 / 8 | 7 / 8 |
| not_owned | 4 / 6 | 1 / 6 |
| not_owned_other | 6 / 8 | 5 / 8 |
| handoff | 3 / 8 | 5 / 8 |
| chit_chat | 7 / 8 | 7 / 8 |
| score | 2 / 6 | 4 / 6 |
| today | 7 / 8 | 8 / 8 |
| sell | 8 / 8 | 8 / 8 |
| sell_other | 5 / 8 | 8 / 8 |
| follow_up | 6 / 6 | 6 / 6 |
| no history | 41 / 51 | 41 / 51 |
| with history | 33 / 47 | 39 / 47 |
| **all** | **74 / 98 (75.5%)** | **80 / 98 (81.6%)** |
| crashes (Ollama could not read a tool call) | 0 | 0 |

## Failures

- **dressme-chat-v3**, why_similar (with history): علاش البونطاكور والدجين الأبيض يتشابهو؟  
  expected ['list_wardrobe', 'explain_similarity'], used ['explain_similarity', 'list_wardrobe', 'explain_similarity'], error: unknown piece 'bottom-bonnet-corn' (use list_wardrobe, or 'last_scan') (27 s)  
  answer: دجين أبيض وبونطاكور: يتشابهو 40% في التصاور. يشتركو في: الموتيف. يختلفو في: النوع.
- **dressme-chat-v3**, why_similar (with history): علاش الحاجة إلي صورتها تشبه لالسويت البلو مارين؟  
  expected ['list_wardrobe', 'explain_similarity'], used ['explain_similarity', 'list_wardrobe', 'explain_similarity'], error: unknown piece 'navy-joggers' (use list_wardrobe, or 'last_scan') (27 s)  
  answer: الحوايج متاعك والسويت البلو مارين يتشابهو ب99% في التصاور. يشتركو في: النوع، اللون والموتيف. المودال متاع التصاور يشوف الحوايج متاعك دجين، وستريت وستريش.
- **dressme-chat-v3**, similar (no history): Trouve des pièces comme mon dernier scan  
  expected ['find_similar'], used ['find_similar'], error: no such item or analysed photo (9 s)  
  answer: Je ne vois pas de pièce que tu as scannée. Prends-la en photo dans l'appli, ou dis-moi à la place ce que tu veux.
- **dressme-chat-v3**, similar (no history): Win nal9a 7aja kif elli sawartha?  
  expected ['find_similar'], used ['find_similar'], error: no such item or analysed photo (11 s)  
  answer: ما لقيتش حاجة اسمها 7aja في الخزانة متاعك. صورها في الخانة متاع السكان، ومبعد عاود اسألني.
- **dressme-chat-v3**, buy (no history): Should I buy this?  
  expected ['buy_advice_last_scan'], used ['buy_advice_last_scan'], error: no analysed photo in the last 24 hours (9 s)  
  answer: I don't see any scanned piece in the last 24 hours. Take a photo in the Scan tab, then ask me again.
- **dressme-chat-v3**, buy (with history): Should I buy this?  
  expected ['buy_advice_last_scan'], used [] (5 s)  
  answer: I'd skip it: this black smart shoes doesn't add a good outfit to your wardrobe. Better keep your budget for something you'll wear more.
- **dressme-chat-v3**, not_owned (with history): Does my cream trousers go with my beige sweatshirt?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'list_wardrobe'] (13 s)  
  answer: I can't find a beige sweatshirt in your wardrobe. Your tops: multicoloured top. Want me to try one of them?
- **dressme-chat-v3**, not_owned (with history): نجم نلبس السويتر الأبيض مع البالرينة؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (18 s)  
  answer: سويتر أكحل وبالرينة: 50/100. باش تحسنها، خلي الحوايج ستيلهم مشترك وزيادة توب ولا سروال.
- **dressme-chat-v3**, not_owned_other (with history): وين نشري حاجة تشبه لالجيلي الأخضر؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (16 s)  
  answer: للبيع توا: شنوة من H&M (74/100) وفولار مونطو من H&M (74/100).
- **dressme-chat-v3**, not_owned_other (with history): Where can I buy something similar to my pink cape?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (15 s)  
  answer: For sale now: nothing that looks like your pink cape. Try one of these instead: Regular cardigan at H&M (black) or Wide coat at H&M (red).
- **dressme-chat-v3**, handoff (no history): What is my wardrobe made of?  
  expected [], used ['list_wardrobe'] (13 s)  
  answer: You have 13 pieces: tops: navy shirt, t-shirt, blue sweatshirt, blue sweater, white top and black top; bottoms: brown cropped trousers, beige leggings, pink jog
- **dressme-chat-v3**, handoff (no history): وريني الإعلانات متاعي  
  expected [], used ['list_wardrobe', 'search_listings'] (15 s)  
  answer: ما لقيت حتى شي موجود يتطابق توا. جرب بلاش حد السوم ولا لون آخر.
- **dressme-chat-v3**, handoff (no history): J'ai des pièces qui se ressemblent trop ?  
  expected [], used ['list_wardrobe', 'find_similar'] (15 s)  
  answer: En vente en ce moment : Wide flip-flops, Relaxed shoes et Cropped heels (H&M).
- **dressme-chat-v3**, handoff (no history): De quoi est faite ma garde-robe ?  
  expected [], used ['list_wardrobe'] (11 s)  
  answer: Tu as 8 pièces : hauts: t-shirt noir et chemise blanche; bas: pantalon rouge, jogging noir et short; vestes et manteaux: blazer violet; chaussures: tongs marron
- **dressme-chat-v3**, handoff (no history): Chnowa fiha el khzena mte3i?  
  expected [], used ['list_wardrobe'] (18 s)  
  answer: عندك 14 حوايج: توبات: سويت أكحل، تونيك برتقالي، تيشرت أزرق، سويتر أحمر وتونيك بوردو; سراول: جيب وليقينغ; روبات: روبة وكومبينيزون روز; صبابط: صباط أزرق، بالرينة 
- **dressme-chat-v3**, chit_chat (no history): شنوة تنجم تعمل؟  
  expected [], used ['suggest_outfits'] (8 s)  
  answer: جرب روبة بيضاء وصباط بالكعب الأكحل: تاخو 95/100.
- **dressme-chat-v3**, score (with history): السورية البيضاء مع السويتر الكريمي، باهي؟  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe', 'score_outfit'], error: these pieces can't be worn together: 2 items of top (max 1) (20 s)  
  answer: ما تنجمش تلبس سورية بيضاء وسويتر كريمي في نفس الوقت (2 حوايج من نوع توب (الأقصى 1)): اختار واحد.
- **dressme-chat-v3**, score (no history): السويت الأكحل مع السورية الموف، باهي؟  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe', 'score_outfit'], error: these pieces can't be worn together: 2 items of top (max 1) (18 s)  
  answer: ما تنجمش تلبس سويت أكحل وسورية موف في نفس الوقت (2 حوايج من نوع توب (الأقصى 1)): اختار واحد.
- **dressme-chat-v3**, score (with history): Is my blue joggers with my blue sneakers a good match?  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe'] (8 s)  
  answer: I can't find any blue sneakers in your wardrobe.
- **dressme-chat-v3**, score (with history): Can I wear my brown shirt with my top?  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe', 'score_outfit'], error: these pieces can't be worn together: 2 items of top (max 1) (17 s)  
  answer: You can't wear your brown shirt and your top at the same time (2 items of top (max 1)): choose one of them.
- **dressme-chat-v3**, today (with history): Je m'habille comment aujourd'hui avec ce temps ?  
  expected ['get_weather', 'suggest_outfits'], used ['get_weather'] (8 s)  
  answer: Aujourd'hui à Tunis : nuageux, de 1 à 10°C. Pas de pluie prévue.
- **dressme-chat-v3**, sell_other (with history): Je veux vendre une autre pièce  
  expected ['pieces_to_sell'], used [] (4 s)  
  answer: Fais une demande pour chaque pièce dans l'onglet Garde-robe.
- **dressme-chat-v3**, sell_other (with history): Je veux vendre une autre pièce  
  expected ['pieces_to_sell'], used [] (4 s)  
  answer: Chaque pièce a une fenêtre de prix : je peux en choisir un. Quelle pièce veux-tu vendre ?
- **dressme-chat-v3**, sell_other (with history): I want to sell a different item  
  expected ['pieces_to_sell'], used [] (5 s)  
  answer: I can only sell pieces that go with nothing in your wardrobe, or the second of each pair of near-identical pieces. Want me to try one of them?
- **dressme-chat-v4**, why_similar (no history): شنوة يجمع التيشرت الأحمر والتوب الأكحل؟  
  expected ['list_wardrobe', 'explain_similarity'], used ['list_wardrobe', 'explain_similarity', 'list_wardrobe'], error: unknown piece '37a3d9faba09890ffc65b234' (use list_wardrobe, or 'last_scan') (22 s)  
  answer: ما لقيتش توب أكحل في الخزانة متاعك. التوبات متاعك: توب أكحل.
- **dressme-chat-v4**, similar (no history): Trouve des pièces comme mon dernier scan  
  expected ['find_similar'], used ['find_similar'], error: no such item or analysed photo (9 s)  
  answer: Je ne trouve pas de pièce scannée. Prends-la en photo dans l'onglet Scanner, puis redemande-moi.
- **dressme-chat-v4**, similar (no history): Win nal9a 7aja kif elli sawartha?  
  expected ['find_similar'], used ['buy_advice_last_scan'] (10 s)  
  answer: نخليها: هالكابريّة البلو مارين ما تزيد حتى لبسة باهية للخزانة متاعك. خلي فلوسك لحاجة تلبسها أكثر.
- **dressme-chat-v4**, buy (no history): Should I buy this?  
  expected ['buy_advice_last_scan'], used ['buy_advice_last_scan'], error: no analysed photo in the last 24 hours (9 s)  
  answer: I don't see any scanned piece from the last 24 hours. Take a photo in the Scan tab, then ask me again.
- **dressme-chat-v4**, not_owned (with history): Does my cream trousers go with my beige sweatshirt?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (18 s)  
  answer: Your cream trousers and your beige sweatshirt: 74/100. That's fine. Note: the pieces have quite different styles. Add shoes to finish the look.
- **dressme-chat-v4**, not_owned (with history): نجم نلبس السويتر الأبيض مع البالرينة؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (19 s)  
  answer: سويتر أكحل وبالرينة: 50/100. موش أحسن حاجة. ملاحظة: الحوايج ستيلهم مختلف برشا وناقص توب ولا سروال.
- **dressme-chat-v4**, not_owned (no history): Does my cream cropped trousers go with my beige shoes?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (19 s)  
  answer: Together, your cream cropped trousers and your blue sandals get 66/100. That's fine. Note: the pieces have quite different styles and missing a top or a bottom.
- **dressme-chat-v4**, not_owned (with history): Mes chaussures grises avec mon haut crème, ça passe ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (19 s)  
  answer: Ensemble, ta chemise crème et ta robe grise font 75/100. Ça passe. Attention : les pièces ont des styles assez différents. Ajoute des chaussures pour finir la t
- **dressme-chat-v4**, not_owned (with history): Mes sandales bleues avec mon jean marron, ça passe ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (18 s)  
  answer: Ensemble, tes sandales bleues et ton portefeuille font 30/100. Ce n'est pas l'idéal. Attention : pas de pièce principale.
- **dressme-chat-v4**, not_owned_other (with history): وين نشري حاجة تشبه لالجيلي الأخضر؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (18 s)  
  answer: للبيع توا: Fitted shorts بH&M (74% شبهلها) وFitted trousers بH&M (74% شبهلها).
- **dressme-chat-v4**, not_owned_other (no history): بقداش نجم نبيع التونيك البرتقالي؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'price_hint'] (17 s)  
  answer: لتونيك برتقالي، الحوايج متاع الفريب تقول من 26 ل30 دينار (الوسط 28 دينار، من 3 حوايج).
- **dressme-chat-v4**, not_owned_other (with history): Where can I buy something similar to my pink cape?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (18 s)  
  answer: For sale now: Regular cardigan at H&M (72% like your pink cape) and Wide coat at H&M (71% like your pink cape).
- **dressme-chat-v4**, handoff (no history): وريني الإعلانات متاعي  
  expected [], used ['list_wardrobe', 'search_listings'] (15 s)  
  answer: ما لقيت حتى شي موجود يتطابق توا.
- **dressme-chat-v4**, handoff (no history): J'ai des pièces qui se ressemblent trop ?  
  expected [], used ['list_wardrobe', 'find_similar'] (16 s)  
  answer: En vente en ce moment : Relaxed cropped trousers, Regular leggings et Classic trousers (H&M).
- **dressme-chat-v4**, handoff (no history): Chnowa fiha el khzena mte3i?  
  expected [], used ['list_wardrobe'] (18 s)  
  answer: عندك 14 حوايج: توبات: سويت أكحل، تونيك أصفر، تيشرت أزرق، سويتر أحمر وتونيك بوردو; سراول: جيب وليقينغ; روبات: روبة وسويت روز; صبابط: صباط أزرق، بالاتوب موف، صباط
- **dressme-chat-v4**, chit_chat (no history): شنوة تنجم تعمل؟  
  expected [], used ['suggest_outfits'] (8 s)  
  answer: جرب روبة بيضاء وصباط بالكعب أكحل: تاخو 95/100.
- **dressme-chat-v4**, score (with history): السورية البيضاء مع السويتر الكريمي، باهي؟  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe', 'score_outfit'], error: these pieces can't be worn together: 2 items of top (max 1) (20 s)  
  answer: ما تنجمش تلبس سورية بيضاء وسويتر كريمي في نفس الوقت (2 حوايج من نوع توب (الأقصى 1)): اختار واحد.
- **dressme-chat-v4**, score (with history): Can I wear my brown shirt with my top?  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe', 'score_outfit'], error: these pieces can't be worn together: 2 items of top (max 1) (20 s)  
  answer: Tu ne peux pas porter ta chemise marron et ton haut en même temps (2 pièces de type haut (max 1)) : choisis-en un.
