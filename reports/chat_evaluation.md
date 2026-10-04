# Chat model evaluation

30 test conversations of `src/build_chat_dataset.py` (wardrobes never seen in training, ~1/3 of the questions phrased differently from the training split). Each assistant turn is one decision; the model sees the real conversation up to that point.

| Model | Tool decision | Tool name | Arguments | Language | s / decision |
|---|---|---|---|---|---|
| qwen3:4b-instruct | 76.0% | 33.3% | 13.9% | 94.9% | 8.55 |

## qwen3:4b-instruct by scenario

| Scenario | Tool decision | Tool name | Arguments | Language |
|---|---|---|---|---|
| buy | 83.3% | 60.0% | 60.0% | 100.0% |
| chit_chat | 100.0% | - | - | 100.0% |
| list | 85.7% | 66.7% | 66.7% | 100.0% |
| not_owned | 60.0% | 0.0% | 0.0% | 100.0% |
| score | 60.9% | 21.4% | 0.0% | 88.9% |
| suggest | 85.2% | 33.3% | 0.0% | 93.3% |

Examples (expected / model):

- **Q:** Une tenue pour un mariage ?
  - expected: Pour un mariage, mon meilleur choix : ton t-shirt noir, ton legging bordeaux et tes chaussures habillées noires (95/100). Les couleurs vont bien ensemble. Sinon : ton sweat noir, ton legging bordeaux, tes chaussures habillées noires et ton manteau bordeaux (83/100). Tu veux une autre idée ?
  - model: Voici une tenue de mariage parfaite avec ce que tu as déjà :

✅ **Top** : T-shirt noir  
✅ **Bottom** : Leggings burgundines  
✅ **Chaussures** : Chaussures formelles noires  

C’est élégant, sobre et parfait pour un mariage. Tu n’as pas besoin de rien acheter ! 😊  

Tu veux aussi une tenue pour un autre événement ?
- **Q:** Donne-moi 4 idées de tenues
  - expected: Essaie ton pull, ton jogging noir et tes sandales bleues : ça fait 95/100. Sinon : ton haut noir, ton jogging noir et tes sandales bleues (94/100). Tu veux une autre idée ?
  - model: Voici 4 idées de tenues que tu peux essayer avec ce que tu as déjà :

1. **Sweater + Pant de course + Sandales bleues**  
   → Un look confortable et élégant pour une journée en plein air.

2. **T-shirt noir + Pant de course noir + Sandales bleues**  
   → Simple, sobre, parfait pour un déjeuner ou un week-end.

3. **Sweater + Pant de course + Sandales bleues**  
   → Idéal pour un temps frais ou une sortie en famille.

4. **T-shirt noir + Pant de course + Sandales bleues**  
   → Un combo classique, facile à porter et à reutiliser.

Tu as déjà tout ce qu’il faut ! Pas besoin de nouveaux achats. 😊
- **Q:** Nechrih walla le?
  - expected: نخليها: هالبونطاكور ما تزيد حتى لبسة باهية للخزانة متاعك. خلي فلوسك لحاجة تلبسها أكثر.
  - model: اللابس اللي تفكرتش فيه (الكابريز) ممكن تمرّي عليه، ونقدر نستخدم ما عندك من ملابس بس. هل تحب نختار لك لبسة من ما عندك؟ 😊
- **Q:** Mon pull bleu va avec ma chemise noire ?
  - expected: Tu ne peux pas porter ton pull bleu et ta chemise noire en même temps (2 pièces de type haut (max 1)) : choisis-en un.
  - model: Non, ton pull bleu et ta chemise noire ne peuvent pas être portés ensemble — c’est trop de tops (un seul top est autorisé par règle de modeste).  

Pourquoi ? Parce que porter deux vêtements de haut (pull + chemise) est trop dévoilant selon les normes de modesté en Tunisie.  

👉 Solution : Mélange ton pull bleu avec un bas (comme tes jeans beige) pour un look simple, élégant et respectueux.  
Exemple : Pull bleu + jeans beige = élégant, modeste, et tu n’as pas besoin d’acheter ! 💡  

Tu veux que je suggère d'autres combinaisons ? 😊
- **Q:** Je peux mettre mon jogging crème avec mes chaussures habillées rouges ?
  - expected: Ensemble, ton jogging crème et tes chaussures habillées rouges font 60/100. Ça passe. Attention : les pièces ont des styles assez différents et il manque un haut ou un bas.
  - model: Oui, tu peux porter ton jogging crème avec tes chaussures habillées rouges !  
Mais attention : le score de l'ensemble est de **59,7/100**, car le jogging et les chaussures ont des styles très différents.  
Tu n’as pas encore de vêtement (comme un haut) pour compléter l’ensemble.  

👉 Pour un look plus équilibré, ajoute un haut blanc ou un sweat (comme ton sweat blanc) !  
C’est déjà dans ton garde-robe, donc tu n’as pas besoin de acheter de nouveau.  

Tu es déjà bien équipé ! 😊
- **Q:** Mon sweat gris avec mon t-shirt violet, ça passe ?
  - expected: Tu ne peux pas porter ton sweat gris et ton t-shirt violet en même temps (2 pièces de type haut (max 1)) : choisis-en un.
  - model: Not quite, actually — you can't wear two tops (like your grey sweatshirt and violet t-shirt) at the same time. That would be too much layering and might not look balanced.

Try pairing one of them with your black shorts or trousers instead. For example:
- Violet t-shirt + black shorts → casual, cool, and easy to match.
- Grey sweatshirt + trousers → a bit more relaxed and comfortable.

Let me know if you'd like help picking a full outfit! 😊

Synthetic data measures tool use and language, not how natural the answers sound: also try a few real questions in the app (CHAT_ENGINE=ollama).
