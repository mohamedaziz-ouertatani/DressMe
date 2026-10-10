# Chat models end to end

Whole chats through the app's engine and the agents' real tools, with no help (see `src/phase4/evaluate_chat_e2e.py`). A chat is right when the model calls exactly the reference tools in order, no tool answers an error and the answer is not empty. 8 chats per scenario (fewer when a wardrobe cannot make it), the same chats for every model, temperature 0.3 (a rerun can differ by a chat or two).

| Scenario | dressme-chat-v2 | dressme-chat-v3 |
|---|---|---|
| why_similar | 8 / 8 | 8 / 8 |
| similar | 6 / 8 | 7 / 8 |
| search | 8 / 8 | 8 / 8 |
| buy | 8 / 8 | 8 / 8 |
| not_owned | 0 / 5 | 5 / 5 |
| not_owned_other | 0 / 8 | 5 / 8 |
| handoff | 7 / 8 | 7 / 8 |
| chit_chat | 8 / 8 | 8 / 8 |
| score | 8 / 8 | 7 / 8 |
| today | 8 / 8 | 7 / 8 |
| **all** | **61 / 77 (79.2%)** | **70 / 77 (90.9%)** |
| crashes (Ollama could not read a tool call) | 0 | 0 |

## Failures

- **dressme-chat-v2**, similar: Trouve-moi quelque chose comme mes baskets bleues  
  expected ['list_wardrobe', 'find_similar'], used ['find_similar'], error: no such item or analysed photo (11 s)  
  answer: Je ne trouve rien qui ressemble à tes baskets bleues dans la base de données des vendeurs (seulement les vêtements vendus en boutique ou en friperie sont dans l
- **dressme-chat-v2**, similar: لقالي حاجة كيف السروال الأبيض  
  expected ['list_wardrobe', 'find_similar'], used ['find_similar'], error: no such item or analysed photo (43 s)  
  answer: ما لقيتش سروال أبيض في الخزانة متاعك. تحب نلقالك حوايج تشبهلها في الحوايج متاعك ولا في الحوايج متاع الخزانة متاع الخزانة متاع الخزانة متاع الخزانة متاع الخزانة 
- **dressme-chat-v2**, not_owned: Je peux mettre mes chaussures avec mon pull kaki ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (19 s)  
  answer: Ensemble, tes chaussures et ton pantalon beige font 51/100. Ce n'est pas l'idéal : les pièces ont des styles assez différents et il manque un haut ou un bas.
- **dressme-chat-v2**, not_owned: Can I wear my beige jacket with my black glasses?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (23 s)  
  answer: Together, your beige coat and your black glasses get 64/100. Not the best match: the pieces have quite different styles and no main piece.
- **dressme-chat-v2**, not_owned: Is my green shirt with my beige swimsuit a good match?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (18 s)  
  answer: Your green shirt and your beige swimsuit: 82/100. That's good!
- **dressme-chat-v2**, not_owned: Is my red waistcoat with my purple shirt a good match?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'], error: these pieces can't be worn together: 2 items of top (max 1) (18 s)  
  answer: You can't wear your purple shirt and your black sweatshirt at the same time (2 items of top (max 1)). Choose one of them.
- **dressme-chat-v2**, not_owned: Can I wear my grey blazer with my brown shorts?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'score_outfit'] (17 s)  
  answer: Together, your brown shorts and your sweatshirt get 61/100. Not the best match: the pieces have quite different styles. Add shoes to finish the look.
- **dressme-chat-v2**, not_owned_other: شنوة يمشي مع السورية الكحلة؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'complete_outfit'] (21 s)  
  answer: مع سورية كحلة، زيد صاك كومبينيزون أكحل: اللبسة تاخو 88/100. زادة تنجم: ليقينغ أكحل (82/100) وجوقينغ أبيض (78/100).
- **dressme-chat-v2**, not_owned_other: Où acheter un truc qui ressemble à mes tongs bleu canard ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (21 s)  
  answer: En vente en ce moment : Tongs crème à 24 TND (friperie à Sfax) et Chaussures habillées grise à 6 TND (friperie à Sousse). Pièces proches chez H&M : Slim flip-fl
- **dressme-chat-v2**, not_owned_other: Où acheter un truc qui ressemble à mes chaussures habillées bleu marine ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (20 s)  
  answer: En vente en ce moment : Baskets violette à 21 TND (friperie à Sfax) et Chaussures habillées grise à 6 TND (friperie à Sousse). Pièces proches chez H&M : Relaxed
- **dressme-chat-v2**, not_owned_other: بقداش نجم نبيع الجيلي الأبيض؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'price_hint'] (18 s)  
  answer: لبيع جيلي أبيض، الحوايج إلي تشبهلها تقول من 36 ل40 دينار (الوسط 39 دينار، من 4 حوايج).
- **dressme-chat-v2**, not_owned_other: Find me something like my black shirt  
  expected ['list_wardrobe'], used ['find_similar'], error: no such item or analysed photo (9 s)  
  answer: I can't find anything that looks like your black shirt: either it's not in your wardrobe or you haven't scanned it yet. Take a photo of it in the Scan tab and t
- **dressme-chat-v2**, not_owned_other: قداش نحط سوم السروال الأخضر؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'price_hint'] (14 s)  
  answer: لسروال أخضر، الحوايج إلي تشبهلها تقول من 35 ل46 دينار (الوسط 39 دينار، من 3 حوايج).
- **dressme-chat-v2**, not_owned_other: Où acheter un truc qui ressemble à mon gilet bleu marine ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (21 s)  
  answer: En vente en ce moment : Blazer noir à 116 TND (Hamadi Abid) et Blazer bleu marine à 195 TND (Hamadi Abid). Pièces proches chez H&M : Cropped blazer, Relaxed coa
- **dressme-chat-v2**, not_owned_other: لقالي حاجة كيف التوب الأبيض  
  expected ['list_wardrobe'], used ['find_similar'], error: no such item or analysed photo (10 s)  
  answer: ما لقيتش توب أبيض في الخزانة متاعك. تحب نلقالك حوايج تشبهلها في الحوايج متاعك ولا في الحوايج إلي صورتها؟
- **dressme-chat-v2**, handoff: Montre-moi mes annonces  
  expected [], used ['list_wardrobe'] (8 s)  
  answer: Tu n'as pas encore de vêtements traditionnels dans ta garde-robe.
- **dressme-chat-v3**, similar: لقالي حاجة كيف السروال الأبيض  
  expected ['list_wardrobe', 'find_similar'], used ['find_similar'], error: no such item or analysed photo (10 s)  
  answer: ما لقيتش سروال أبيض في الخزانة متاعك. صوره في الخانة متاع السكان، ولا اسألني.
- **dressme-chat-v3**, not_owned_other: شنوة يمشي مع السورية الكحلة؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'complete_outfit'] (19 s)  
  answer: مع سورية كحلة، زيد فيستة مارونية: اللبسة تاخو 87/100. زادة تنجم: شورط رمادي (81/100) وسويت أكحل (81/100).
- **dressme-chat-v3**, not_owned_other: Où acheter un truc qui ressemble à mes tongs bleu canard ?  
  expected ['list_wardrobe'], used ['list_wardrobe', 'find_similar'] (22 s)  
  answer: En vente en ce moment : Tongs crème à 24 TND (friperie à Sfax) et Chaussures habillées grise à 6 TND (friperie à Sousse). Pièces proches chez H&M : Slim flip-fl
- **dressme-chat-v3**, not_owned_other: بقداش نجم نبيع الجيلي الأبيض؟  
  expected ['list_wardrobe'], used ['list_wardrobe', 'price_hint'] (18 s)  
  answer: لجيلي أبيض، الحوايج إلي تشبهلها تقول من 20 ل25 دينار (الوسط 24 دينار، من 6 حوايج).
- **dressme-chat-v3**, handoff: Montre-moi mes annonces  
  expected [], used ['list_wardrobe'] (13 s)  
  answer: Tu as 12 pièces : hauts: chemise marron, t-shirt beige, pull, t-shirt blanc, pull violet et t-shirt noir; bas: jupe grise; vestes et manteaux: gilet blanc; sacs
- **dressme-chat-v3**, score: Je peux mettre ma jupe bleu marine avec mes sandales bordeaux ?  
  expected ['list_wardrobe', 'score_outfit'], used ['list_wardrobe'] (13 s)  
  answer: Je ne trouve pas des sandales bordeaux dans ta garde-robe. Tes chaussures : tongs grises, baskets rouges et sandales bordeaux. Tu veux que j'en essaie un ?
- **dressme-chat-v3**, today: What should I wear today?  
  expected ['get_weather', 'suggest_outfits'], used ['get_weather'] (8 s)  
  answer: I can't get today's weather right now. Try again in a few minutes.
