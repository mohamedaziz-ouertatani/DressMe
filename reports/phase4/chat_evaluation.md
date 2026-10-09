# Chat model evaluation

150 test conversations of `src/phase4/build_chat_dataset.py` (wardrobes never seen in training, ~1/3 of the questions phrased differently from the training split). Each assistant turn is one decision; the model sees the real conversation up to that point.

| Model | Tool decision | Tool name | Arguments | Language | Router | s / decision |
|---|---|---|---|---|---|---|
| qwen3:4b-instruct | 79.5% | 46.1% | 26.7% | 78.1% | 80.0% | 10.77 |
| dressme-chat | 58.4% | 69.4% | 57.8% | 90.9% | 70.0% | 4.86 |
| dressme-chat-v2 | 98.0% | 97.2% | 92.8% | 98.8% | 90.0% | 5.44 |

## qwen3:4b-instruct by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 80.0% | - | - | 25.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 87.5% | 71.4% | 71.4% | 75.0% | - |
| analyst / stats | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / twins | 83.3% | 66.7% | 66.7% | 66.7% | - |
| explainer / chit_chat | 100.0% | - | - | 66.7% | - |
| explainer / how_scoring | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / labels | 54.5% | 14.3% | 14.3% | 100.0% | - |
| explainer / why_score | 94.3% | 59.1% | 40.9% | 84.6% | - |
| explainer / why_verdict | 80.0% | 50.0% | 50.0% | 100.0% | - |
| router / route | - | - | - | - | 80.0% |
| seller / chit_chat | 100.0% | - | - | 50.0% | - |
| seller / price | 80.0% | 50.0% | 30.0% | 100.0% | - |
| seller / sell | 100.0% | 40.0% | 0.0% | 100.0% | - |
| seller / what_sell | 75.0% | 50.0% | 50.0% | 50.0% | - |
| shopping / buy | 85.7% | 66.7% | 66.7% | 50.0% | - |
| shopping / chit_chat | 100.0% | - | - | 33.3% | - |
| shopping / handoff | 0.0% | - | - | - | - |
| shopping / search | 84.6% | 63.6% | 0.0% | 80.0% | - |
| shopping / similar | 81.0% | 36.4% | 36.4% | 80.0% | - |
| stylist / chit_chat | 100.0% | - | - | 100.0% | - |
| stylist / complete | 66.7% | 25.0% | 0.0% | 75.0% | - |
| stylist / follow_up | 76.9% | 33.3% | 0.0% | 71.4% | - |
| stylist / list | 80.6% | 57.1% | 14.3% | 70.6% | - |
| stylist / not_owned | 50.0% | 0.0% | 0.0% | 100.0% | - |
| stylist / score | 44.4% | 16.7% | 0.0% | 66.7% | - |
| stylist / suggest | 88.5% | 53.8% | 23.1% | 76.9% | - |
| stylist / today | 69.0% | 50.0% | 50.0% | 90.9% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! How can I help you today? 😊
- **Q:** Je veux mettre ma tunique vert olive, j'ajoute quoi ?
  - expected: Le meilleur avec ta tunique vert olive : tes gants orange (76/100).
  - model: Avec ta tunique vert olive, tu peux la porter avec des **baskets** ou un **short** (tu en as un ?).  

Mais pour compléter ton look, on peut ajouter simplement **des gants orange** (tu en as déjà un !) — c’est un détail qui donne du charme sans coûter cher.  

👉 Si tu veux, je peux t’aider à trouver un short ou des baskets dans ta friperie préférée.  
Tu veux que je t’aide à choisir ? 😊
- **Q:** Can I wear my red shirt with my pink leggings?
  - expected: Together, your red shirt and your pink leggings get 55/100. Not the best match. Note: the pieces have quite different styles and red and pink clash. Add shoes to finish the look.
  - model: Your red shirt and pink leggings would score 54.6 out of 100 — not a bad match, but the colours clash a bit, and the styles are very different. Also, you don’t have any shoes to complete it!  

To make it better, try pairing it with:  
- A pair of grey sneakers (you already have one)  
- A neutral accessory like a simple bracelet or a watch  

If you want, I can suggest a full outfit with what you already own. Would you like that? 😊
- **Q:** علاش التطبيقة قالت هكا على الحاجة إلي صورتها؟
  - expected: "خليها" خاطر تعمل 0 لبسة باهية فيها خير من حوايجك؛ "اشري" يلزمها 5. 1 زايدين يبدلو الرأي. عندك ديجا حاجة تشبهلها برشا: ليقينغ.
  - model: التطبيقة قالت "skip" لأنها لم تجد أي ملابس جيدة تُستخدم معها (0 ملابس مقبولة)، ورغم أن هناك ملابس مشابهة (مثلاً جينز بسيط) في ملابسك، إلا أن هذه الأحذية لا تُستخدم في أي ملابس مقبولة.  

السبب: لا توجد ملابس تُستخدم معها لتكوين ملابس مقبولة (أقل من 5 ملابس مقبولة)، ورغم أن هناك ملابس مشابهة، إلا أن هذه الأحذية لا تُستخدم في أي ملابس مقبولة.  

إذا أردت، يمكنني مساعدتك في تغيير ملابسك أو تحسينها! 😊
- **Q:** Hi!
  - expected: Hi! I can tell you what your wardrobe is missing, which pieces you use most or never, what it is made of and which pieces you own twice. What do you want to know?
  - model: Hi there! 😊 How can I help you today with your wardrobe or fashion choices? (In French, English, or Darija!) 🌟
- **Q:** Je m'habille comment aujourd'hui avec ce temps ?
  - expected: Aujourd'hui à Tunis : nuageux, de 24 à 33°C. Pas de pluie prévue. Je partirais sur ton pull crème, ton jean bleu et tes chaussures habillées beiges (94/100). Les couleurs vont bien ensemble.
  - model: Aujourd’hui, avec un temps ensoleillé et nuageux à Tunis (32°C), voici une suggestion d’habillement à budget :

- **Un sweater crème** (ton sur ton)  
- **Des blue jeans** (classiques, facile à porter)  
- **Des chaussures beige** (souple, parfait pour la chaleur)

👉 C’est un look léger, élégant et parfait pour une journée en plein air.  
Tu as déjà tout ce qu’il faut ! 🌤️👖🧣

Tu veux un autre style (ex : plus casual ou plus simple) ?

## dressme-chat by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 20.0% | - | - | 100.0% | - |
| analyst / handoff | 0.0% | - | - | - | - |
| analyst / insights | 50.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / stats | 60.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / twins | 50.0% | 66.7% | 66.7% | - | - |
| explainer / chit_chat | 0.0% | - | - | - | - |
| explainer / how_scoring | 50.0% | 100.0% | 100.0% | - | - |
| explainer / labels | 68.2% | 42.9% | 42.9% | 100.0% | - |
| explainer / why_score | 65.7% | 36.4% | 36.4% | 100.0% | - |
| explainer / why_verdict | 40.0% | 100.0% | 100.0% | - | - |
| router / route | - | - | - | - | 70.0% |
| seller / chit_chat | 0.0% | - | - | - | - |
| seller / price | 66.7% | 30.0% | 30.0% | - | - |
| seller / sell | 77.3% | 40.0% | 13.3% | 100.0% | - |
| seller / what_sell | 50.0% | 100.0% | 100.0% | - | - |
| shopping / buy | 57.1% | 66.7% | 66.7% | 100.0% | - |
| shopping / chit_chat | 0.0% | - | - | - | - |
| shopping / handoff | 0.0% | - | - | - | - |
| shopping / search | 46.2% | 90.9% | 0.0% | 100.0% | - |
| shopping / similar | 66.7% | 63.6% | 54.5% | 100.0% | - |
| stylist / chit_chat | 0.0% | - | - | - | - |
| stylist / complete | 66.7% | 50.0% | 50.0% | - | - |
| stylist / follow_up | 53.8% | 100.0% | 50.0% | 100.0% | - |
| stylist / list | 58.1% | 100.0% | 85.7% | 75.0% | - |
| stylist / not_owned | 50.0% | 33.3% | 33.3% | - | - |
| stylist / score | 72.2% | 75.0% | 66.7% | 0.0% | - |
| stylist / suggest | 57.7% | 100.0% | 100.0% | 100.0% | - |
| stylist / today | 69.0% | 94.4% | 94.4% | 100.0% | - |
| stylist / weather | 50.0% | 100.0% | 100.0% | - | - |

Examples (expected / model):

- **Q:** Hi!
  - expected: Hi! I can tell you what your wardrobe is missing, which pieces you use most or never, what it is made of and which pieces you own twice. What do you want to know?
  - model: Hi! I can pick an outfit from your wardrobe, tell you if two pieces go together, or help you decide if a piece you want to buy works for you. What do you need?
- **Q:** Montre-moi mes vestes
  - expected: Tes vestes et manteaux : gilet beige.
  - model: </tool_call>

</tool_call>
- **Q:** Une idée de tenue ?
  - expected: Essaie ton t-shirt gris, ton legging kaki et tes sandales bleues : ça fait 92/100. Les couleurs vont bien ensemble. Tu veux une autre idée ?
  - model: Essaie ton t-shirt gris, ton legging kaki et tes sandales bleues : ça fait 92/100.
- **Q:** Choisis-moi une tenue
  - expected: Mon meilleur choix : ton pull marron, ton jean marron et tes baskets beiges (82/100).
  - model: Mon meilleur choix : ton pull marron, ton jean marron et tes baskets beiges (82/100).
- **Q:** نجم نلبس السويتر البلو مارين مع التيشرت الأكحل؟
  - expected: ما تنجمش تلبس سويتر بلو مارين وتيشرت أكحل في نفس الوقت (2 حوايج من نوع توب (الأقصى 1)): اختار واحد.
  - model: </tool_call>

</tool_call>

## dressme-chat-v2 by scenario

| Agent / scenario | Tool decision | Tool name | Arguments | Language | Router |
|---|---|---|---|---|---|
| analyst / chit_chat | 80.0% | - | - | 100.0% | - |
| analyst / handoff | 100.0% | - | - | 100.0% | - |
| analyst / insights | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / stats | 100.0% | 100.0% | 100.0% | 100.0% | - |
| analyst / twins | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / chit_chat | 100.0% | - | - | 100.0% | - |
| explainer / how_scoring | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / labels | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_score | 100.0% | 100.0% | 100.0% | 100.0% | - |
| explainer / why_verdict | 100.0% | 100.0% | 100.0% | 100.0% | - |
| router / route | - | - | - | - | 90.0% |
| seller / chit_chat | 100.0% | - | - | 100.0% | - |
| seller / price | 100.0% | 100.0% | 90.0% | 100.0% | - |
| seller / sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| seller / what_sell | 100.0% | 100.0% | 100.0% | 100.0% | - |
| shopping / buy | 100.0% | 66.7% | 66.7% | 100.0% | - |
| shopping / chit_chat | 100.0% | - | - | 100.0% | - |
| shopping / handoff | 50.0% | - | - | 100.0% | - |
| shopping / search | 100.0% | 100.0% | 63.6% | 93.3% | - |
| shopping / similar | 95.2% | 72.7% | 72.7% | 90.0% | - |
| stylist / chit_chat | 100.0% | - | - | 100.0% | - |
| stylist / complete | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / follow_up | 92.3% | 100.0% | 83.3% | 100.0% | - |
| stylist / list | 100.0% | 100.0% | 85.7% | 100.0% | - |
| stylist / not_owned | 50.0% | 100.0% | 100.0% | - | - |
| stylist / score | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / suggest | 100.0% | 92.3% | 92.3% | 100.0% | - |
| stylist / today | 100.0% | 100.0% | 100.0% | 100.0% | - |
| stylist / weather | 100.0% | 100.0% | 100.0% | 100.0% | - |

Examples (expected / model):

- **Q:** Thanks!
  - expected: You're welcome! Have a great day.
  - model: You're welcome! Have a great day.
- **Q:** Je veux mettre ma tunique vert olive, j'ajoute quoi ?
  - expected: Le meilleur avec ta tunique vert olive : tes gants orange (76/100).
  - model: Avec ta tunique vert olive, ajoute tes gants orange : la tenue fait 76/100.
- **Q:** Can I wear my red shirt with my pink leggings?
  - expected: Together, your red shirt and your pink leggings get 55/100. Not the best match. Note: the pieces have quite different styles and red and pink clash. Add shoes to finish the look.
  - model: Your red shirt and your pink leggings: 55/100. Not the best match. Note: the pieces have quite different styles and red and pink clash. Add shoes to finish the look.
- **Q:** علاش التطبيقة قالت هكا على الحاجة إلي صورتها؟
  - expected: "خليها" خاطر تعمل 0 لبسة باهية فيها خير من حوايجك؛ "اشري" يلزمها 5. 1 زايدين يبدلو الرأي. عندك ديجا حاجة تشبهلها برشا: ليقينغ.
  - model: "خليها" خاطر تعمل 0 لبسة باهية فيها؛ "اشري" يلزمها 5. 1 أكثر من اللازم للبيع.
- **Q:** Hi!
  - expected: Hi! I can tell you what your wardrobe is missing, which pieces you use most or never, what it is made of and which pieces you own twice. What do you want to know?
  - model: Hi! I can tell you what your wardrobe is missing, which pieces you use most or never, and which pieces you own twice. What do you want to know?
- **Q:** Je m'habille comment aujourd'hui avec ce temps ?
  - expected: Aujourd'hui à Tunis : nuageux, de 24 à 33°C. Pas de pluie prévue. Je partirais sur ton pull crème, ton jean bleu et tes chaussures habillées beiges (94/100). Les couleurs vont bien ensemble.
  - model: Aujourd'hui à Tunis : nuageux, de 24 à 33°C. Pas de pluie prévue. Mon meilleur choix : ton pull crème, ton jean bleu et tes chaussures habillées beiges (94/100).

Synthetic data measures tool use and language, not how natural the answers sound: also try a few real questions in the app (CHAT_ENGINE=ollama).
