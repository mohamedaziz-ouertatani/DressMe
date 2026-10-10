# Chat model evaluation

150 test conversations of `src/phase4/build_chat_dataset.py` (wardrobes never seen in training, ~1/3 of the questions phrased differently from the training split). Each assistant turn is one decision; the model sees the real conversation up to that point.

| Model | Tool decision | Tool name | Arguments | Language | Router | s / decision |
|---|---|---|---|---|---|---|
| dressme-chat-v3 | 96.5% | 92.6% | 81.8% | 94.3% | 75.0% | 5.8 |
| dressme-chat-v4 | 98.8% | 96.6% | 89.2% | 96.9% | 75.0% | 5.8 |

## dressme-chat-v3 by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 100.0% | - | - | 100.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / stats | 87.5% | 75.0% | 75.0% | 75.0% | - |
| analyst / twins | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / chit_chat | 100.0% | - | - | 75.0% | - |
| explainer / how_scoring | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / labels | 100.0% | 100.0% | 90.0% | 100.0% | - |
| explainer / what_if | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_score | 100.0% | 100.0% | 87.5% | 100.0% | - |
| explainer / why_similar | 100.0% | 92.9% | 78.6% | 85.7% | - |
| explainer / why_verdict | 100.0% | 100.0% | 100.0% | 100.0% | - |
| router / route | - | - | - | - | 75.0% |
| seller / handoff | 50.0% | - | - | 100.0% | - |
| seller / my_listings | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / not_owned_other | 100.0% | 100.0% | 66.7% | 100.0% | - |
| seller / price | 100.0% | 100.0% | 87.5% | 100.0% | - |
| seller / sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / sell_other | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / what_sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / buy | 100.0% | 83.3% | 83.3% | 100.0% | - |
| shopping / chit_chat | 100.0% | - | - | 100.0% | - |
| shopping / handoff | 100.0% | - | - | 100.0% | - |
| shopping / not_owned_other | 100.0% | 0.0% | 0.0% | 100.0% | - |
| shopping / search | 95.7% | 100.0% | 40.0% | 91.7% | - |
| shopping / similar | 90.0% | 72.7% | 45.5% | 66.7% | - |
| stylist / chit_chat | 100.0% | - | - | 100.0% | - |
| stylist / complete | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / follow_up | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / handoff | 100.0% | - | - | 100.0% | - |
| stylist / list | 91.7% | 90.9% | 90.9% | 100.0% | - |
| stylist / not_owned | 50.0% | 100.0% | 100.0% | - | - |
| stylist / not_owned_other | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / score | 93.9% | 90.0% | 80.0% | 100.0% | - |
| stylist / suggest | 100.0% | 100.0% | 81.8% | 90.9% | - |
| stylist / today | 90.5% | 85.7% | 85.7% | 85.7% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! Have a great day.
- **Q:** J'ai scanné une pièce, ça vaut le coup ?
  - expected: Réfléchis bien : ce pantalon beige ne fait que 2 bonne(s) tenue(s) avec ta garde-robe, comme ta chemise grise. En friperie, on peut rarement rendre une pièce.
  - model: Réfléchis bien : ce pantalon beige ne fait que 2 bonne(s) tenue(s) avec ta garde-robe, comme ta chemise grise. En friperie, on peut rarement rendre une pièce.
- **Q:** Can you list my clothes?
  - expected: Here is what you own (8 pieces): tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
  - model: You have 8 pieces: tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
- **Q:** What should I wear today?
  - expected: Today in Tunis: cloudy, 13 to 20°C. No rain expected. I'd go with your grey top, your navy jeans and your brown blazer (81/100). Note: no shoes.
  - model: Today in Tunis: cloudy, 13 to 20°C. No rain expected. Try your grey top, your navy jeans and your brown blazer: it scores 81/100. Note: no shoes.
- **Q:** Ma jupe crème va avec mes chaussures bleues ?
  - expected: Ta jupe crème et tes chaussures bleues : 59/100. Ce n'est pas l'idéal. Attention : les pièces ont des styles assez différents et il manque un haut ou un bas.
  - model: Ensemble, ta jupe crème et tes chaussures bleues font 59/100. Ça passe. Attention : les pièces ont des styles assez différents et il manque un haut ou un bas.
- **Q:** علاش الجيب والتونيك البرتقالي يتشابهو؟
  - expected: جيب وتونيك برتقالي: يتشابهو 41% في التصاور. يشتركو في: الموتيف. يختلفو في: الصنف والنوع.
  - model: جيب وتونيك برتقالي: يتشابهو في الموتيفات متاعهم. يختلفو في النوع والسلال.

## dressme-chat-v4 by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 100.0% | - | - | 100.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / stats | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / twins | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / chit_chat | 100.0% | - | - | 75.0% | - |
| explainer / how_scoring | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / labels | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / what_if | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_score | 100.0% | 87.5% | 87.5% | 100.0% | - |
| explainer / why_similar | 100.0% | 100.0% | 92.9% | 100.0% | - |
| explainer / why_verdict | 100.0% | 100.0% | 100.0% | 100.0% | - |
| router / route | - | - | - | - | 75.0% |
| seller / handoff | 100.0% | - | - | 100.0% | - |
| seller / my_listings | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / not_owned_other | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / price | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / sell_other | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / what_sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / buy | 100.0% | 83.3% | 83.3% | 100.0% | - |
| shopping / chit_chat | 100.0% | - | - | 100.0% | - |
| shopping / handoff | 100.0% | - | - | 100.0% | - |
| shopping / not_owned_other | 50.0% | 100.0% | 100.0% | - | - |
| shopping / search | 95.7% | 100.0% | 40.0% | 100.0% | - |
| shopping / similar | 100.0% | 81.8% | 63.6% | 66.7% | - |
| stylist / chit_chat | 100.0% | - | - | 100.0% | - |
| stylist / complete | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / follow_up | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / handoff | 100.0% | - | - | 100.0% | - |
| stylist / list | 100.0% | 100.0% | 90.9% | 100.0% | - |
| stylist / not_owned | 50.0% | 100.0% | 100.0% | - | - |
| stylist / not_owned_other | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / score | 100.0% | 100.0% | 95.0% | 100.0% | - |
| stylist / suggest | 100.0% | 100.0% | 81.8% | 100.0% | - |
| stylist / today | 95.2% | 92.9% | 92.9% | 85.7% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! Have a great day.
- **Q:** J'ai scanné une pièce, ça vaut le coup ?
  - expected: Réfléchis bien : ce pantalon beige ne fait que 2 bonne(s) tenue(s) avec ta garde-robe, comme ta chemise grise. En friperie, on peut rarement rendre une pièce.
  - model: Réfléchis bien : ce pantalon beige ne fait que 2 bonnes tenues avec ta garde-robe, comme ta chemise grise. En friperie, on peut rarement rendre une pièce.
- **Q:** Can you list my clothes?
  - expected: Here is what you own (8 pieces): tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
  - model: Here is what you own (8 pieces): tops: black t-shirt, t-shirt and black tunic; bottoms: purple jeans and red skirt; dresses: white dress and navy jumpsuit; shoes: white ballet flats.
- **Q:** What should I wear today?
  - expected: Today in Tunis: cloudy, 13 to 20°C. No rain expected. I'd go with your grey top, your navy jeans and your brown blazer (81/100). Note: no shoes.
  - model: Today in Tunis: cloudy, 13 to 20°C. No rain expected. Try your grey top, your navy jeans and your brown blazer: it scores 81/100. Note: no shoes.
- **Q:** Ma jupe crème va avec mes chaussures bleues ?
  - expected: Ta jupe crème et tes chaussures bleues : 59/100. Ce n'est pas l'idéal. Attention : les pièces ont des styles assez différents et il manque un haut ou un bas.
  - model: Ensemble, ta jupe crème et tes chaussures bleues font 59/100. Ce n'est pas l'idéal. Attention : les pièces ont des styles assez différents et il manque un haut ou un bas.
- **Q:** علاش الجيب والتونيك البرتقالي يتشابهو؟
  - expected: جيب وتونيك برتقالي: يتشابهو 41% في التصاور. يشتركو في: الموتيف. يختلفو في: الصنف والنوع.
  - model: جيب وتونيك برتقالي: يتشابهو 41% في التصاور. يشتركو في: الموتيف. يختلفو في: النوع والتصنيف.

Synthetic data measures tool use and language, not how natural the answers sound: also try a few real questions in the app (CHAT_ENGINE=ollama).
