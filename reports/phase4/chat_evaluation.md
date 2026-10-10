# Chat model evaluation

150 test conversations of `src/phase4/build_chat_dataset.py` (wardrobes never seen in training, ~1/3 of the questions phrased differently from the training split). Each assistant turn is one decision; the model sees the real conversation up to that point.

| Model | Tool decision | Tool name | Arguments | Language | Router | s / decision |
|---|---|---|---|---|---|---|
| qwen3:4b-instruct | 79.0% | 48.7% | 27.0% | 74.2% | 33.3% | 10.94 |
| dressme-chat-v2 | 95.7% | 95.2% | 89.9% | 100.0% | 100.0% | 5.29 |
| dressme-chat-v3 | 97.0% | 95.2% | 88.4% | 99.4% | 66.7% | 5.17 |

## qwen3:4b-instruct by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 100.0% | - | - | 50.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 84.2% | 62.5% | 62.5% | 70.0% | - |
| analyst / stats | 81.8% | 60.0% | 60.0% | 50.0% | - |
| explainer / chit_chat | 100.0% | - | - | 0.0% | - |
| explainer / how_scoring | 71.4% | 33.3% | 33.3% | 75.0% | - |
| explainer / labels | 100.0% | 50.0% | 50.0% | 100.0% | - |
| explainer / what_if | 0.0% | 0.0% | 0.0% | - | - |
| explainer / why_score | 100.0% | 87.5% | 25.0% | 100.0% | - |
| explainer / why_similar | 83.3% | 25.0% | 25.0% | 100.0% | - |
| explainer / why_verdict | 75.0% | 33.3% | 33.3% | 100.0% | - |
| router / route | - | - | - | - | 33.3% |
| seller / chit_chat | 100.0% | - | - | 0.0% | - |
| seller / handoff | 100.0% | - | - | 100.0% | - |
| seller / my_listings | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / not_owned_other | 40.0% | 0.0% | 0.0% | 0.0% | - |
| seller / price | 85.7% | 25.0% | 25.0% | 40.0% | - |
| seller / sell | 100.0% | 53.3% | 0.0% | 87.5% | - |
| seller / what_sell | 87.5% | 66.7% | 66.7% | 80.0% | - |
| shopping / buy | 94.4% | 88.9% | 88.9% | 77.8% | - |
| shopping / chit_chat | 100.0% | - | - | 0.0% | - |
| shopping / search | 82.6% | 60.0% | 0.0% | 76.9% | - |
| shopping / similar | 81.8% | 53.8% | 46.2% | 66.7% | - |
| stylist / chit_chat | 100.0% | - | - | 66.7% | - |
| stylist / complete | 60.0% | 16.7% | 0.0% | 62.5% | - |
| stylist / follow_up | 75.0% | 50.0% | 0.0% | 100.0% | - |
| stylist / handoff | 100.0% | - | - | 100.0% | - |
| stylist / list | 86.2% | 69.2% | 15.4% | 68.8% | - |
| stylist / not_owned | 83.3% | 60.0% | 0.0% | 100.0% | - |
| stylist / score | 44.1% | 9.1% | 0.0% | 66.7% | - |
| stylist / suggest | 81.5% | 53.8% | 15.4% | 71.4% | - |
| stylist / today | 70.6% | 50.0% | 50.0% | 78.6% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! How can I help you today? 😊
- **Q:** J'ai scanné une pièce, ça vaut le coup ?
  - expected: Je passerais mon tour : ce gilet blanc n'ajoute pas de bonne tenue à ta garde-robe. Garde ton budget pour une pièce que tu porteras plus.
  - model: Non, cette cardigan blanc ne vaut pas le coup. Elle ne s'harmonise pas avec rien de ce que tu as déjà, et tu n'as pas besoin d'ajouter une pièce qui ne s'intègre pas à ton style. Tu peux la laisser de côté.
- **Q:** What's in my wardrobe?
  - expected: Here is what you own (8 pieces): tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
  - model: Here’s what’s in your wardrobe:

- **Top**:  
  - Black t-shirt (solid)  
  - Solid t-shirt (colour not visible)  
  - Black checked tunic  

- **Bottom**:  
  - Purple jeans (solid)  
  - Red printed skirt  

- **Outerwear**:  
  - None  

- **Shoes**:  
  - White flats (solid)  

- **Dresses**:  
  - White solid dress  
  - Navy floral jumpsuit  

You’ve got a great mix of casual and stylish pieces — perfect for everyday wear or light outings! Want a suggestion for today’s outfit? 😊
- **Q:** السويتر الأكحل يمشي مع الليقينغ الأصفر؟
  - expected: مع بعضهم، سويتر أكحل وليقينغ أصفر ياخذو 88/100. يمشيو مزيان! زيد صباط باش تكمل اللبسة.
  - model: Oui, ton sweater noir et tes leggings jaunes font un excellent mélange ! 🌟  
C’est un look élégant et moderne, avec un contraste joli entre le noir et le jaune.  

⚠️ Mais attention : il manque des chaussures !  
👉 Tu peux ajouter des sandales noires ou des sneakers noires (tu en as déjà dans ton garde-robe).  

Score total : 88/100 ✅  
→ Style : 81% (très bon)  
→ Couleur : parfait (noir + jaune = équilibré)  
→ Motif : parfait (tous solides)  
→ Structure : 75% (un peu léger, mais ça marche pour un look casual)  

Tu veux que je suggère un autre combo avec un autre article ? 😊
- **Q:** De quoi est faite ma garde-robe ?
  - expected: Tu as 5 pièces : hauts 1, bas 3, chaussures 1. Couleurs principales : bleu, bleu marine et marron. 2 sont des couleurs neutres qui vont avec presque tout.
  - model: Ta garde-robe est faite de :

- **1 t-shirt** (blanc, bleu, marron, teal)  
- **3 bas** (bleu, marron, noir)  
- **1 chaussure** (marron)  

Tu as principalement des **teintes solides**, avec un peu de **motif**.  
Les couleurs neutres (bleu marine, blanc) sont utiles pour tout type d’occasion.  
Tu as 4 pièces sans couleur définie, 4 sans niveau de couverture, 3 sans saison, et 4 sans usage.  

👉 Tu as besoin de **plus de tops** ou de **chaussures** pour compléter ton look !  
👉 Tu as déjà un bon équilibre avec des pièces solides, donc pense à les réutiliser plutôt que de les remplacer.  

Tu veux que je t’aide à créer un look aujourd’hui ? 😊
- **Q:** Write me a poem about the sea
  - expected: Sorry, I can only help with clothes: outfits, your wardrobe and what to buy. Want an outfit idea for today?
  - model: Sure! Here's a simple and beautiful poem about the sea, in Tunisian Arabic:

**البحر**  
يا بحر، يا مَنْ تَسْكُنُ في القلبِ  
تَرْتَحِلُ في المَساءِ، تَسْكُنُ في الصَّبَّارِ  
تَسْكُنُ في المَدِّ، تَغَيّرُ في المَرَّةِ  
كُلُّ مَرَّةٍ تَسْكُنُ في القلبِ  

تَرْتَحِلُ بِالضوءِ، تَسْكُنُ في السَّمَاءِ  
تَسْكُنُ في المَرَّةِ، تَسْكُنُ في الحُزنِ  
كُلُّ مَرَّةٍ تَسْكُنُ في القلبِ،  
وَتَسْكُنُ في القلبِ، وَتَسْكُنُ في القلبِ  

يا بحر، يا مَنْ تَسْكُنُ في القلبِ  
تَرْتَحِلُ في المَساءِ، تَسْكُنُ في الصَّبَّارِ  

I hope you enjoy it! 🌊💙

## dressme-chat-v2 by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 100.0% | - | - | 100.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / stats | 100.0% | 60.0% | 60.0% | 100.0% | - |
| explainer / chit_chat | 100.0% | - | - | 100.0% | - |
| explainer / how_scoring | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / labels | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / what_if | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_score | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_similar | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_verdict | 100.0% | 100.0% | 100.0% | 100.0% | - |
| router / route | - | - | - | - | 100.0% |
| seller / chit_chat | 100.0% | - | - | 100.0% | - |
| seller / handoff | 0.0% | - | - | - | - |
| seller / my_listings | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / not_owned_other | 60.0% | 100.0% | 100.0% | 100.0% | - |
| seller / price | 92.9% | 100.0% | 87.5% | 100.0% | - |
| seller / sell | 95.7% | 100.0% | 93.3% | 100.0% | - |
| seller / what_sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / buy | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / chit_chat | 100.0% | - | - | 100.0% | - |
| shopping / search | 100.0% | 100.0% | 70.0% | 100.0% | - |
| shopping / similar | 95.5% | 69.2% | 69.2% | 100.0% | - |
| stylist / chit_chat | 100.0% | - | - | 100.0% | - |
| stylist / complete | 95.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / follow_up | 100.0% | 100.0% | 75.0% | 100.0% | - |
| stylist / handoff | 100.0% | - | - | 100.0% | - |
| stylist / list | 100.0% | 100.0% | 92.3% | 100.0% | - |
| stylist / not_owned | 58.3% | 100.0% | 100.0% | 100.0% | - |
| stylist / score | 97.1% | 95.5% | 86.4% | 100.0% | - |
| stylist / suggest | 100.0% | 100.0% | 92.3% | 100.0% | - |
| stylist / today | 91.2% | 90.0% | 90.0% | 100.0% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! Have a great day.
- **Q:** J'ai scanné une pièce, ça vaut le coup ?
  - expected: Je passerais mon tour : ce gilet blanc n'ajoute pas de bonne tenue à ta garde-robe. Garde ton budget pour une pièce que tu porteras plus.
  - model: Je passerais mon tour : ce gilet blanc n'ajoute pas de bonne tenue à ta garde-robe. Garde ton budget pour une pièce que tu porteras plus.
- **Q:** What's in my wardrobe?
  - expected: Here is what you own (8 pieces): tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
  - model: You have 8 pieces: tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
- **Q:** السويتر الأكحل يمشي مع الليقينغ الأصفر؟
  - expected: مع بعضهم، سويتر أكحل وليقينغ أصفر ياخذو 88/100. يمشيو مزيان! زيد صباط باش تكمل اللبسة.
  - model: سويتر أكحل وليقينغ أصفر: 88/100. يمشيو مزيان! زيد صباط باش تكمل اللبسة.
- **Q:** De quoi est faite ma garde-robe ?
  - expected: Tu as 5 pièces : hauts 1, bas 3, chaussures 1. Couleurs principales : bleu, bleu marine et marron. 2 sont des couleurs neutres qui vont avec presque tout.
  - model: Tu as 5 pièces : hauts 1, bas 3, chaussures 1. Couleurs principales : bleu, bleu marine et marron. 4 sont des couleurs neutres qui vont avec presque tout.
- **Q:** Write me a poem about the sea
  - expected: Sorry, I can only help with clothes: outfits, your wardrobe and what to buy. Want an outfit idea for today?
  - model: I'm sorry, I can only help with clothes: outfits, your wardrobe and what to sell. Want an outfit idea for today?

## dressme-chat-v3 by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 100.0% | - | - | 100.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / stats | 100.0% | 80.0% | 80.0% | 100.0% | - |
| explainer / chit_chat | 100.0% | - | - | 50.0% | - |
| explainer / how_scoring | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / labels | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / what_if | 100.0% | 50.0% | 0.0% | 100.0% | - |
| explainer / why_score | 92.9% | 87.5% | 87.5% | 100.0% | - |
| explainer / why_similar | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_verdict | 100.0% | 100.0% | 100.0% | 100.0% | - |
| router / route | - | - | - | - | 66.7% |
| seller / chit_chat | 100.0% | - | - | 100.0% | - |
| seller / handoff | 0.0% | - | - | - | - |
| seller / my_listings | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / not_owned_other | 80.0% | 100.0% | 100.0% | 100.0% | - |
| seller / price | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / sell | 95.7% | 93.3% | 86.7% | 100.0% | - |
| seller / what_sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / buy | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / chit_chat | 100.0% | - | - | 100.0% | - |
| shopping / search | 100.0% | 100.0% | 70.0% | 100.0% | - |
| shopping / similar | 95.5% | 76.9% | 76.9% | 100.0% | - |
| stylist / chit_chat | 100.0% | - | - | 100.0% | - |
| stylist / complete | 95.0% | 100.0% | 91.7% | 100.0% | - |
| stylist / follow_up | 100.0% | 100.0% | 75.0% | 100.0% | - |
| stylist / handoff | 100.0% | - | - | 100.0% | - |
| stylist / list | 100.0% | 100.0% | 84.6% | 100.0% | - |
| stylist / not_owned | 83.3% | 100.0% | 80.0% | 100.0% | - |
| stylist / score | 100.0% | 100.0% | 90.9% | 100.0% | - |
| stylist / suggest | 100.0% | 100.0% | 92.3% | 100.0% | - |
| stylist / today | 91.2% | 90.0% | 90.0% | 100.0% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! Have a great day.
- **Q:** J'ai scanné une pièce, ça vaut le coup ?
  - expected: Je passerais mon tour : ce gilet blanc n'ajoute pas de bonne tenue à ta garde-robe. Garde ton budget pour une pièce que tu porteras plus.
  - model: Je passerais mon tour : ce gilet blanc n'ajoute pas de bonne tenue à ta garde-robe.
- **Q:** What's in my wardrobe?
  - expected: Here is what you own (8 pieces): tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
  - model: You have 8 pieces: tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
- **Q:** السويتر الأكحل يمشي مع الليقينغ الأصفر؟
  - expected: مع بعضهم، سويتر أكحل وليقينغ أصفر ياخذو 88/100. يمشيو مزيان! زيد صباط باش تكمل اللبسة.
  - model: مع بعضهم، سويتر أكحل وليقينغ أصفر ياخذو 88/100. باهي. زيد صباط باش تكمل اللبسة.
- **Q:** De quoi est faite ma garde-robe ?
  - expected: Tu as 5 pièces : hauts 1, bas 3, chaussures 1. Couleurs principales : bleu, bleu marine et marron. 2 sont des couleurs neutres qui vont avec presque tout.
  - model: Tu as 5 pièces : 1 hauts, 3 bas, 1 chaussures. Couleurs principales : bleu, bleu marine, marron, blanc et vert bouteille. 4 sont des couleurs neutres qui vont avec presque tout.
- **Q:** Write me a poem about the sea
  - expected: Sorry, I can only help with clothes: outfits, your wardrobe and what to buy. Want an outfit idea for today?
  - model: I'm sorry, I can't write poems. Try the Explainer: it can help you with that.

Synthetic data measures tool use and language, not how natural the answers sound: also try a few real questions in the app (CHAT_ENGINE=ollama).
