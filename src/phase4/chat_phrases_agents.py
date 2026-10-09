"""
Sentences for the agents' new scenarios in src/phase4/build_chat_dataset.py (weather,
complete an outfit, listings, look-alikes, wardrobe analysis, selling, explanations,
hand-offs between agents, the router). Same rules as src/phase4/chat_phrases.py: plain
data, every template keeps its {slots}, "arabizi" questions are answered in Darija.

TEAM: ALL the Darija in this file is NEW (2026-10-08) and NOT REVIEWED by a native
speaker. It is listed in reports/phase4/darija_review.md ("New phrases for the agents");
please correct it there or here, then rebuild the dataset.
"""

# ------------------------------------------------------------------ agent names
AGENT_NAMES = {   # how an answer names another assistant
    "stylist": {"en": "the Stylist", "fr": "le Styliste", "ar": "الستيليست"},
    "shopping": {"en": "the Shopping advisor", "fr": "le Conseiller shopping", "ar": "مستشار الشراء"},
    "analyst": {"en": "the Wardrobe analyst", "fr": "l'Analyste de garde-robe", "ar": "محلل الخزانة"},
    "seller": {"en": "the Seller assistant", "fr": "l'Assistant de vente", "ar": "مساعد البيع"},
    "explainer": {"en": "the Explainer", "fr": "l'Explicateur", "ar": "المفسّر"},
}
SAY_HANDOFF = {   # the question belongs to another agent: one sentence, no tool
    "en": ["That's a question for {agent}: ask it there and it will answer you.",
           "{Agent} handles that: ask it and it will help you."],
    "fr": ["C'est une question pour {agent} : pose-la-lui et il te répondra.",
           "{Agent} s'en occupe : demande-lui et il t'aidera."],
    "ar": ["هاذا سؤال ل{agent}: اسألو هو ويجاوبك.", "{agent} هو إلي يتلهى بهاذا: اسألو ويعاونك."],
}
SAY_HELLO_AGENT = {   # greeting by agent (the Stylist keeps chat_phrases.SAY_HELLO)
    "shopping": {
        "en": "Hi! I can tell you if a piece you scanned is worth buying, find clothes for sale in "
              "shops and friperie, and find look-alikes of your pieces. What are you looking for?",
        "fr": "Salut ! Je peux te dire si une pièce scannée vaut le coup, trouver des vêtements en "
              "vente en boutique et en friperie, et des pièces qui ressemblent aux tiennes. Tu cherches quoi ?",
        "ar": "عسلامة! نجم نقلك إذا الحاجة إلي صورتها تستاهل تشريها، نلقالك حوايج للبيع في الحوانت "
              "والفريب، وحوايج تشبه لحوايجك. شنوة تلوج؟",
    },
    "analyst": {
        "en": "Hi! I can tell you what your wardrobe is missing, which pieces you use most or never, "
              "what it is made of and which pieces you own twice. What do you want to know?",
        "fr": "Salut ! Je peux te dire ce qui manque à ta garde-robe, les pièces que tu portes le plus "
              "ou jamais, de quoi elle est faite et les pièces en double. Qu'est-ce que tu veux savoir ?",
        "ar": "عسلامة! نجم نقلك شنوة ناقص في الخزانة متاعك، شنية الحوايج إلي تلبسها برشا ولا ما تلبسهاش، "
              "شنوة فيها والحوايج إلي عندك منهم زوز. شنوة تحب تعرف؟",
    },
    "seller": {
        "en": "Hi! I can find pieces worth selling, suggest a fair friperie price and prepare the Sell "
              "form for you. Which piece do you want to sell?",
        "fr": "Salut ! Je peux trouver les pièces à vendre, te proposer un prix friperie juste et "
              "préparer le formulaire de vente. Quelle pièce veux-tu vendre ?",
        "ar": "عسلامة! نجم نلقالك الحوايج إلي تنجم تبيعهم، نقترحلك سوم فريب معقول ونحضرلك الفورمولار "
              "متاع البيع. شنية الحاجة إلي تحب تبيعها؟",
    },
    "explainer": {
        "en": "Hi! I can explain why an outfit gets its score, what would change it, why a piece got "
              "its labels and why a scan got its verdict. What should I explain?",
        "fr": "Salut ! Je peux t'expliquer pourquoi une tenue a sa note, ce qui la changerait, pourquoi "
              "une pièce a ses étiquettes et pourquoi un scan a son verdict. Qu'est-ce que je t'explique ?",
        "ar": "عسلامة! نجم نفسرلك علاش لبسة خذات النوطة متاعها، شنوة يبدلها، علاش حاجة خذات الليبال "
              "متاعها وعلاش السكان خذا الرأي متاعو. شنوة نفسرلك؟",
    },
}

# ------------------------------------------------------------------ Stylist: weather
ASK_TODAY = {   # what to wear today -> get_weather, then suggest_outfits(season)
    "en": ["What should I wear today?", "What do I wear today with this weather?",
           "Dress me for today"],
    "fr": ["Je mets quoi aujourd'hui ?", "Je m'habille comment aujourd'hui avec ce temps ?",
           "Habille-moi pour aujourd'hui"],
    "ar": ["شنوة نلبس اليوم؟", "شنوة نلبس اليوم مع هالطقس؟", "لبسني لليوم"],
    "arabizi": ["chnowa nelbes lyoum?", "chnowa nelbes lyoum m3a hel ta9s?", "lebesni lel youm"],
}
ASK_WEATHER = {
    "en": ["What's the weather like today?", "Is it going to rain today?"],
    "fr": ["Il fait quel temps aujourd'hui ?", "Il va pleuvoir aujourd'hui ?"],
    "ar": ["كيفاش الطقس اليوم؟", "باش تصب اليوم؟"],
    "arabizi": ["kifech el ta9s lyoum?", "bech tsob lyoum?"],
}
CONDITION_WORDS = {
    "clear": {"en": "sunny", "fr": "ensoleillé", "ar": "شمس"},
    "cloudy": {"en": "cloudy", "fr": "nuageux", "ar": "مغيّم"},
    "fog": {"en": "foggy", "fr": "brumeux", "ar": "ضباب"},
    "rain": {"en": "rainy", "fr": "pluvieux", "ar": "مطر"},
    "snow": {"en": "snowy", "fr": "neigeux", "ar": "ثلج"},
    "storm": {"en": "stormy", "fr": "orageux", "ar": "عواصف"},
}
SAY_WEATHER = {   # {place}, {condition}, {low}, {high}
    "en": "Today in {place}: {condition}, {low} to {high}°C.",
    "fr": "Aujourd'hui à {place} : {condition}, de {low} à {high}°C.",
    "ar": "اليوم في {place}: {condition}، من {low} ل{high} درجة.",
}
SAY_RAIN = {"en": "Rain is likely, take a jacket.", "fr": "Il risque de pleuvoir, prends une veste.",
            "ar": "ممكن تصب، خوذ فيستة معاك."}
SAY_NO_RAIN = {"en": "No rain expected.", "fr": "Pas de pluie prévue.", "ar": "ما فماش مطر."}
SAY_WEATHER_DOWN = {
    "en": "I can't get today's weather right now, so here is a general pick.",
    "fr": "Je n'arrive pas à avoir la météo du jour, alors voici un choix général.",
    "ar": "ما نجمتش نجيب الطقس متاع اليوم، هاذا اختيار عام.",
}

# ------------------------------------------------------------------ Stylist: complete
ASK_COMPLETE = {   # {a} = "my black jeans" / "ma jupe noire" / "الدجين الكحل"
    "en": ["What goes with {a}?", "Complete an outfit around {a}", "I want to wear {a}, what do I add?"],
    "fr": ["Qu'est-ce qui va avec {a} ?", "Complète une tenue avec {a}", "Je veux mettre {a}, j'ajoute quoi ?"],
    "ar": ["شنوة يمشي مع {a}؟", "كملي لبسة مع {a}", "نحب نلبس {a}، شنوة نزيد؟"],
}
SAY_COMPLETE = {   # {a}, {added}, {score}
    "en": ["With {a}, add {added}: the outfit scores {score}/100.", "Best match for {a}: {added} ({score}/100)."],
    "fr": ["Avec {a}, ajoute {added} : la tenue fait {score}/100.", "Le meilleur avec {a} : {added} ({score}/100)."],
    "ar": ["مع {a}، زيد {added}: اللبسة تاخو {score}/100.", "أحسن حاجة مع {a}: {added} ({score}/100)."],
}
SAY_COMPLETE_OTHER = {"en": "Also good: {others}.", "fr": "Aussi possible : {others}.",
                      "ar": "زادة تنجم: {others}."}
SAY_COMPLETE_NONE = {
    "en": "Nothing else in your wardrobe goes with {a} yet. A piece that matches it would help.",
    "fr": "Rien d'autre dans ta garde-robe ne va avec {a} pour l'instant. Une pièce assortie aiderait.",
    "ar": "حتى حاجة أخرى في الخزانة متاعك ما تمشي مع {a} توا. حاجة تمشي معاها تعاونك.",
}

# ------------------------------------------------------------------ Shopping
ASK_SEARCH = {   # {piece} = "black jeans" (bare), {price} TND
    "en": ["Where can I find {piece}?", "I'm looking for {piece}", "Any {piece} for sale?"],
    "fr": ["Où je peux trouver {piece} ?", "Je cherche {piece}", "Il y a {piece} en vente ?"],
    "ar": ["وين نلقى {piece}؟", "نلوج على {piece}", "فما {piece} للبيع؟"],
}
ASK_SEARCH_PRICE = {
    "en": ["I need {piece} under {price} TND", "Find me {piece} for less than {price} TND"],
    "fr": ["Il me faut {piece} à moins de {price} TND", "Trouve-moi {piece} pour moins de {price} TND"],
    "ar": ["نحب {piece} بأقل من {price} دينار", "لقالي {piece} بأقل من {price} دينار"],
}
SAY_SEARCH = {   # {n} found, {list}
    "en": "In stock now: {list}.", "fr": "En stock en ce moment : {list}.", "ar": "موجود توا: {list}.",
}
SAY_LISTING = {   # one listing: {title}, {price}, {where}
    "en": "{title} at {price} TND ({where})", "fr": "{title} à {price} TND ({where})",
    "ar": "{title} ب{price} دينار ({where})",
}
SAY_FRIPERIE_IN = {"en": "friperie seller in {city}", "fr": "friperie à {city}", "ar": "فريب في {city}"}
SAY_SNAPSHOT = {
    "en": "Some prices come from an old snapshot, so stock may have changed.",
    "fr": "Certains prix viennent d'un ancien relevé : le stock a pu changer.",
    "ar": "شوية أسوام جاية من صورة قديمة، ممكن الستوك تبدل.",
}
SAY_SEARCH_NONE = {
    "en": "I found nothing in stock matching that right now. Try without the price limit or another colour.",
    "fr": "Je ne trouve rien en stock qui correspond pour l'instant. Essaie sans limite de prix ou une autre couleur.",
    "ar": "ما لقيت حتى شي موجود يتطابق توا. جرب بلاش حد السوم ولا لون آخر.",
}
ASK_SIMILAR = {   # {a} = one of their items
    "en": ["Find me something like {a}", "Where can I buy something similar to {a}?"],
    "fr": ["Trouve-moi quelque chose comme {a}", "Où acheter un truc qui ressemble à {a} ?"],
    "ar": ["لقالي حاجة كيف {a}", "وين نشري حاجة تشبه ل{a}؟"],
}
ASK_SIMILAR_SCAN = {
    "en": ["Where can I find something like the piece I scanned?", "Find look-alikes of my last scan"],
    "fr": ["Où trouver une pièce comme celle que j'ai scannée ?", "Trouve des pièces comme mon dernier scan"],
    "ar": ["وين نلقى حاجة كيف إلي صورتها؟", "لقالي حوايج تشبه للسكان الأخير"],
    "arabizi": ["win nal9a 7aja kif elli sawartha?", "la9ali 7wayej tchabah lel scan le5er"],
}
SAY_SIMILAR = {   # {shop} H&M names, {listings}
    "en": "Look-alikes at H&M: {shop}.", "fr": "Pièces proches chez H&M : {shop}.",
    "ar": "حوايج تشبهلها في H&M: {shop}.",
}
SAY_SIMILAR_LISTINGS = {"en": "For sale now: {listings}.", "fr": "En vente en ce moment : {listings}.",
                        "ar": "للبيع توا: {listings}."}
SAY_SIMILAR_NONE = {
    "en": "I found no look-alike for it right now.", "fr": "Je ne trouve pas de pièce proche pour l'instant.",
    "ar": "ما لقيت حتى حاجة تشبهلها توا.",
}
SAY_NO_SCAN_SIMILAR = {
    "en": "I don't see a scanned piece. Take a photo in the Scan tab, then ask me again.",
    "fr": "Je ne vois pas de pièce scannée. Prends-la en photo dans l'onglet Scanner, puis redemande-moi.",
    "ar": "ما نشوف حتى حاجة مصورة. صورها في الخانة متاع السكان، ومبعد عاود اسألني.",
}

# ------------------------------------------------------------------ Wardrobe analyst
ASK_INSIGHTS = {
    "en": ["What's missing in my wardrobe?", "Which of my pieces are the most useful?",
           "What should I add to my wardrobe?"],
    "fr": ["Qu'est-ce qui manque dans ma garde-robe ?", "Quelles pièces me servent le plus ?",
           "Je devrais ajouter quoi à ma garde-robe ?"],
    "ar": ["شنوة ناقص في الخزانة متاعي؟", "شنية الحوايج إلي تنفعني أكثر؟", "شنوة لازمني نزيد للخزانة؟"],
    "arabizi": ["chnowa na9es fel khzena mte3i?", "chniya el 7wayej elli tenfa3ni akther?",
                "chnowa lazemni nzid lel khzena?"],
}
SAY_INSIGHTS_OUTFITS = {
    "en": "Your wardrobe makes {good} good outfits.", "fr": "Ta garde-robe fait {good} bonnes tenues.",
    "ar": "الخزانة متاعك تعمل {good} لبسات باهيين.",
}
SAY_VERSATILE = {"en": "Most useful: {items}.", "fr": "Les plus utiles : {items}.",
                 "ar": "أكثر حوايج تنفع: {items}."}
SAY_UNMATCHED = {"en": "Goes with nothing yet: {items}.", "fr": "Ne va encore avec rien : {items}.",
                 "ar": "ما يمشي مع حتى شي توا: {items}."}
MISSING_WORDS = {
    "shoes": {"en": "shoes", "fr": "des chaussures", "ar": "صباط"},
    "top": {"en": "a top", "fr": "un haut", "ar": "توب"},
    "bottom": {"en": "a bottom", "fr": "un bas", "ar": "سروال"},
    "main": {"en": "a top and a bottom, or a dress", "fr": "un haut et un bas, ou une robe",
             "ar": "توب وسروال، ولا روبة"},
}
SAY_MISSING = {"en": "To make more outfits, add {missing}.", "fr": "Pour plus de tenues, ajoute {missing}.",
               "ar": "باش تعمل لبسات أكثر، زيد {missing}."}
SAY_NOTHING_MISSING = {"en": "Nothing essential is missing.", "fr": "Rien d'essentiel ne manque.",
                       "ar": "ما ناقصك حتى شي أساسي."}
ASK_STATS = {
    "en": ["What is my wardrobe made of?", "How many clothes do I have, and in which colours?"],
    "fr": ["De quoi est faite ma garde-robe ?", "J'ai combien de vêtements, et de quelles couleurs ?"],
    "ar": ["شنوة فيها الخزانة متاعي؟", "قداش عندي من حاجة، وشنية الألوان؟"],
    "arabizi": ["chnowa fiha el khzena mte3i?", "9addech 3andi men 7aja, w chniya el alwen?"],
}
SAY_STATS = {   # {total}, {categories}, {colours}
    "en": "You have {total} pieces: {categories}. Main colours: {colours}.",
    "fr": "Tu as {total} pièces : {categories}. Couleurs principales : {colours}.",
    "ar": "عندك {total} حوايج: {categories}. الألوان الأساسية: {colours}.",
}
SAY_NEUTRAL = {"en": "{n} of them are neutral colours that go with almost anything.",
               "fr": "{n} sont des couleurs neutres qui vont avec presque tout.",
               "ar": "{n} منهم ألوان نوترال يمشيو مع كل شي تقريبا."}
SAY_TO_CONFIRM = {"en": "{n} pieces still have no colour: you can set it in the Wardrobe tab.",
                  "fr": "{n} pièces n'ont pas encore de couleur : tu peux la choisir dans l'onglet Garde-robe.",
                  "ar": "{n} حوايج ما عندهمش لون توا: تنجم تختارو في الخانة متاع الخزانة."}
ASK_TWINS = {
    "en": ["Do I own the same thing twice?", "Any duplicates in my wardrobe?"],
    "fr": ["Est-ce que j'ai des vêtements en double ?", "J'ai des pièces qui se ressemblent trop ?"],
    "ar": ["عندي حوايج مكررين؟", "فما حوايج يتشابهو برشا عندي؟"],
    "arabizi": ["3andi 7wayej mkarrin?", "famma 7wayej yetchabhou barcha 3andi?"],
}
SAY_TWINS = {"en": "These look almost the same: {pairs}.", "fr": "Ces pièces se ressemblent beaucoup : {pairs}.",
             "ar": "هاذوما يتشابهو برشا: {pairs}."}
SAY_NO_TWINS = {"en": "No duplicates: all your pieces look different.",
                "fr": "Pas de doublons : toutes tes pièces sont différentes.",
                "ar": "ما فماش حوايج مكررة: الكل مختلفين."}

# ------------------------------------------------------------------ Seller assistant
ASK_WHAT_SELL = {
    "en": ["What should I sell?", "Which clothes could I sell?"],
    "fr": ["Qu'est-ce que je devrais vendre ?", "Quels vêtements je pourrais vendre ?"],
    "ar": ["شنوة لازمني نبيع؟", "شنية الحوايج إلي نجم نبيعهم؟"],
    "arabizi": ["chnowa lazemni nbi3?", "chniya el 7wayej elli najem nbi3hom?"],
}
SAY_SELL_UNMATCHED = {"en": "{items} go with nothing in your wardrobe.",
                      "fr": "{items} ne vont avec rien dans ta garde-robe.",
                      "ar": "{items} ما يمشيو مع حتى شي في الخزانة متاعك."}
SAY_SELL_TWINS = {"en": "You also own near-copies: you could sell {items}.",
                  "fr": "Tu as aussi des quasi-doublons : tu pourrais vendre {items}.",
                  "ar": "عندك زادة حوايج يتشابهو: تنجم تبيع {items}."}
SAY_SELL_NOTHING = {"en": "Every piece you own is useful in your outfits: I wouldn't sell any for now.",
                    "fr": "Toutes tes pièces servent dans tes tenues : je n'en vendrais aucune pour l'instant.",
                    "ar": "الحوايج متاعك الكل ينفعو في اللبسات: ما نبيع حتى شي توا."}
SAY_SELL_NEXT = {"en": "Want a price for one of them?", "fr": "Tu veux un prix pour l'une d'elles ?",
                 "ar": "تحب نقلك بقداش تنجم تبيع وحدة منهم؟"}
ASK_PRICE = {   # {a} = one of their items
    "en": ["How much can I sell {a} for?", "What price for {a}?"],
    "fr": ["Je peux vendre {a} combien ?", "Quel prix pour {a} ?"],
    "ar": ["بقداش نجم نبيع {a}؟", "قداش نحط سوم {a}؟"],
}
SAY_PRICE = {   # {a}, {low}, {high}, {median}, {count}
    "en": "For {a}, similar listings suggest {low} to {high} TND (middle: {median} TND, from {count} look-alikes).",
    "fr": "Pour {a}, les annonces proches donnent {low} à {high} TND (milieu : {median} TND, sur {count} pièces proches).",
    "ar": "ل{a}، الحوايج إلي تشبهلها تقول من {low} ل{high} دينار (الوسط {median} دينار، من {count} حوايج).",
}
SAY_PRICE_NONE = {
    "en": "I can't find similar listings with a price for {a} yet, so I can't suggest a fair price.",
    "fr": "Je ne trouve pas encore d'annonces proches avec un prix pour {a}, je ne peux pas proposer de prix juste.",
    "ar": "ما لقيتش حوايج تشبه ل{a} عندها سوم، ما نجمش نقترح سوم معقول.",
}
ASK_SELL = {   # sell one piece: price, then the form
    "en": ["Help me sell {a}", "I want to sell {a}"],
    "fr": ["Aide-moi à vendre {a}", "Je veux vendre {a}"],
    "ar": ["عاوني نبيع {a}", "نحب نبيع {a}"],
}
SAY_SELL_FORM = {   # {title}, {price}
    "en": "I prepared the Sell form: \"{title}\" at {price} TND, the middle of similar listings. Open it with "
          "the button, add your city and contact and send it. An admin checks each listing before others see it.",
    "fr": "J'ai préparé le formulaire de vente : « {title} » à {price} TND, le milieu des annonces proches. Ouvre-le "
          "avec le bouton, ajoute ta ville et ton contact, puis envoie. Un admin vérifie chaque annonce avant qu'elle soit visible.",
    "ar": "حضرتلك الفورمولار متاع البيع: \"{title}\" ب{price} دينار، الوسط متاع الحوايج إلي تشبهلها. حلّو بالبوطون، "
          "زيد المدينة والكونتاكت متاعك وابعثو. أدمين يثبت في كل إعلان قبل ما يشوفوه الناس.",
}
SAY_SELL_ASK_PRICE = {
    "en": "I can't find similar listings with a price for {a}. Tell me your price and I'll prepare the Sell form.",
    "fr": "Je ne trouve pas d'annonces proches avec un prix pour {a}. Dis-moi ton prix et je prépare le formulaire.",
    "ar": "ما لقيتش حوايج تشبه ل{a} عندها سوم. قلي السوم متاعك ونحضرلك الفورمولار.",
}
ASK_MY_LISTINGS = {
    "en": ["Show my listings", "How are my listings doing?"],
    "fr": ["Montre-moi mes annonces", "Où en sont mes annonces ?"],
    "ar": ["وريني الإعلانات متاعي", "شنية أخبار الإعلانات متاعي؟"],
    "arabizi": ["warini les annonces mte3i", "chniya a5bar les annonces mte3i?"],
}
STATUS_WORDS = {
    "pending": {"en": "waiting for an admin", "fr": "en attente d'un admin", "ar": "تستنى في الأدمين"},
    "active": {"en": "visible", "fr": "visible", "ar": "تبان للناس"},
    "rejected": {"en": "rejected", "fr": "refusée", "ar": "مرفوضة"},
    "gone": {"en": "sold or removed", "fr": "vendue ou retirée", "ar": "تباعت ولا تنحات"},
}
SAY_MY_LISTINGS = {"en": "Your listings: {list}.", "fr": "Tes annonces : {list}.", "ar": "الإعلانات متاعك: {list}."}
SAY_MY_LISTING = {"en": "{title}, {price} TND: {status}", "fr": "{title}, {price} TND : {status}",
                  "ar": "{title}، {price} دينار: {status}"}
SAY_REJECTED_NOTE = {"en": "The admin's note: \"{note}\".", "fr": "Note de l'admin : « {note} ».",
                     "ar": "ملاحظة الأدمين: \"{note}\"."}
SAY_NO_LISTINGS = {"en": "You have no listings yet. Ask me what to sell, or use the Sell tab.",
                   "fr": "Tu n'as pas encore d'annonce. Demande-moi quoi vendre, ou utilise l'onglet Vendre.",
                   "ar": "ما عندك حتى إعلان توا. اسألني شنوة تبيع، ولا استعمل الخانة متاع البيع."}
REVIEW_NOTES = ["Photo too dark, please take it again in daylight", "Price missing a size", "Blurry photo"]

# ------------------------------------------------------------------ Explainer
ASK_WHY_SCORE = {   # {a}, {b}
    "en": ["Why does {a} with {b} get that score?", "Explain the score of {a} with {b}"],
    "fr": ["Pourquoi {a} avec {b} a cette note ?", "Explique-moi la note de {a} avec {b}"],
    "ar": ["علاش {a} مع {b} خذات هالنوطة؟", "فسرلي النوطة متاع {a} مع {b}"],
}
PART_WORDS = {
    "style": {"en": "style", "fr": "style", "ar": "الستيل"},
    "colour": {"en": "colours", "fr": "couleurs", "ar": "الألوان"},
    "pattern": {"en": "patterns", "fr": "motifs", "ar": "الموتيفات"},
    "structure": {"en": "structure", "fr": "structure", "ar": "التركيبة"},
}
SAY_WHY_SCORE = {   # {score}, {points} = "style 20/35, colours 18/25..."
    "en": "{score}/100, from {points}.", "fr": "{score}/100, avec {points}.", "ar": "{score}/100، من {points}.",
}
SAY_WORKS = {"en": "What works: {facts}.", "fr": "Ce qui marche : {facts}.", "ar": "شنوة يمشي: {facts}."}
SAY_PROBLEMS = {"en": "What lowers it: {facts}.", "fr": "Ce qui baisse la note : {facts}.",
                "ar": "شنوة ينقص النوطة: {facts}."}
SAY_SWAP = {"en": "Weakest piece: {piece}; {swap} instead would add {gain} points.",
            "fr": "Pièce la plus faible : {piece} ; {swap} à la place ajouterait {gain} points.",
            "ar": "أضعف حاجة: {piece}؛ {swap} في بلاصتها تزيد {gain} نقاط."}
SAY_NO_SWAP = {"en": "No piece of your wardrobe would clearly improve it.",
               "fr": "Aucune pièce de ta garde-robe ne l'améliorerait vraiment.",
               "ar": "حتى حاجة من الخزانة متاعك ما تحسنها بالحق."}
# the Explainer's facts (backend/app/agents/explainer.py FACTS) in French and Darija:
# (regex on the English fact, French, Darija); {0}, {1}... = the groups
FACTS = [
    (r"the pieces share one style", "les pièces ont le même style", "الحوايج عندهم نفس الستيل"),
    (r"the pieces have quite different styles", "les pièces ont des styles assez différents",
     "الحوايج ستيلهم مختلف برشا"),
    (r"the outfit is unlike the user's usual style", "la tenue ne ressemble pas à ton style habituel",
     "اللبسة ما تشبهش للستيل متاعك العادي"),
    (r"(\w+) and (\w+) go together", "le {0} et le {1} vont bien ensemble", "{0} و{1} يمشيو مع بعضهم"),
    (r"a calm base of (\d+) neutral colours", "une base calme de {0} couleurs neutres",
     "قاعدة هادية من {0} ألوان نوترال"),
    (r"(\w+) and (\w+) clash", "le {0} et le {1} ne vont pas ensemble", "{0} و{1} ما يمشيوش مع بعضهم"),
    (r"too many bold colours \((.+)\)", "trop de couleurs vives ({0})", "برشا ألوان قوية ({0})"),
    (r"one statement pattern \((\w+)\)", "un seul motif fort ({0})", "موتيف قوي واحد ({0})"),
    (r"calm, plain pieces", "des pièces calmes et unies", "حوايج هادية وسادة"),
    (r"two bold patterns \((\w+) \+ (\w+)\)", "deux motifs chargés ({0} + {1})", "زوز موتيفات قويين ({0} + {1})"),
    (r"a complete outfit with shoes", "une tenue complète avec chaussures", "لبسة كاملة بالصباط"),
    (r"no shoes", "pas de chaussures", "ما فماش صباط"),
    (r"a full piece and a bottom together", "une pièce entière avec un bas", "روبة مع سروال"),
    (r"(\d+) pieces of ([\w-]+)", "{0} pièces de type {1}", "{0} حوايج من نوع {1}"),
    (r"([\w-]+) and ([\w-]+) don't go together", "{0} et {1} ne vont pas ensemble", "{0} و{1} ما يمشيوش مع بعضهم"),
    (r"no main piece", "pas de pièce principale", "ما فماش حاجة أساسية"),
    (r"missing a top or a bottom", "il manque un haut ou un bas", "ناقص توب ولا سروال"),
]
ASK_WHAT_IF = {   # {c} replaces {b} in {a} + {b}
    "en": ["What if I wear {c} instead of {b} with {a}?"],
    "fr": ["Et si je mets {c} au lieu de {b} avec {a} ?"],
    "ar": ["وكان نلبس {c} في بلاصة {b} مع {a}؟"],
}
SAY_WHAT_IF = {"en": "With {c} instead of {b}: {before} → {after}/100 ({change} points).",
               "fr": "Avec {c} au lieu de {b} : {before} → {after}/100 ({change} points).",
               "ar": "ب{c} في بلاصة {b}: {before} → {after}/100 ({change} نقاط)."}
ASK_LABELS = {   # {a} = one of their items, {field}
    "en": ["Why is {a} labelled like that?", "How sure is the app about {a}?"],
    "fr": ["Pourquoi {a} est étiqueté(e) comme ça ?", "L'appli est sûre de quoi pour {a} ?"],
    "ar": ["علاش {a} خذا هالليبال؟", "قداش التطبيقة متأكدة من {a}؟"],
}
FIELD_WORDS = {
    "category": {"en": "category", "fr": "catégorie", "ar": "الصنف"},
    "sub_category": {"en": "type", "fr": "type", "ar": "النوع"},
    "pattern": {"en": "pattern", "fr": "motif", "ar": "الموتيف"},
    "colour": {"en": "colour", "fr": "couleur", "ar": "اللون"},
}
SAY_LABEL = {"en": "{field}: {value} ({conf}% sure)", "fr": "{field} : {value} (sûr à {conf} %)",
             "ar": "{field}: {value} (متأكد {conf}%)"}
SAY_LABELS = {"en": "The app's guesses from the photo: {labels}.",
              "fr": "Ce que l'appli a deviné sur la photo : {labels}.",
              "ar": "شنوة خمنت التطبيقة من التصويرة: {labels}."}
SAY_UNSURE = {"en": "It is not sure about the {fields}: please check it.",
              "fr": "Elle n'est pas sûre du {fields} : vérifie-le.",
              "ar": "موش متأكدة من {fields}: ثبت فيه."}
SAY_CORRECTED = {"en": "You corrected the {fields} yourself.", "fr": "Tu as corrigé le {fields} toi-même.",
                 "ar": "إنت صلحت {fields} بروحك."}
SAY_OPEN_PANEL = {"en": "Open the explanation to see where the model looked in the picture.",
                  "fr": "Ouvre l'explication pour voir où le modèle a regardé sur la photo.",
                  "ar": "حل التفسير باش تشوف وين خزر المودال في التصويرة."}
ASK_WHY_VERDICT = {
    "en": ["Why did my scan get that verdict?", "Why does the app say that about the piece I scanned?"],
    "fr": ["Pourquoi mon scan a eu ce verdict ?", "Pourquoi l'appli dit ça de la pièce que j'ai scannée ?"],
    "ar": ["علاش السكان متاعي خذا هالرأي؟", "علاش التطبيقة قالت هكا على الحاجة إلي صورتها؟"],
    "arabizi": ["3lech el scan mte3i 5dhe hel ra2y?", "3lech el application 9alet haka 3al 7aja elli sawartha?"],
}
VERDICT_WORDS = {"buy": {"en": "buy", "fr": "acheter", "ar": "اشري"},
                 "think": {"en": "think about it", "fr": "réfléchir", "ar": "خمم"},
                 "skip": {"en": "skip", "fr": "passer", "ar": "خليها"}}
SAY_VERDICT = {   # {verdict}, {good}, {buy_min}
    "en": "\"{verdict}\" because it makes {good} good outfit(s) where it beats what you own; \"buy\" needs {buy_min}.",
    "fr": "« {verdict} » car elle fait {good} bonne(s) tenue(s) où elle bat ce que tu as ; « acheter » en demande {buy_min}.",
    "ar": "\"{verdict}\" خاطر تعمل {good} لبسة باهية فيها خير من حوايجك؛ \"اشري\" يلزمها {buy_min}.",
}
SAY_TO_NEXT = {"en": "{n} more would change the verdict.", "fr": "{n} de plus changerait le verdict.",
               "ar": "{n} زايدين يبدلو الرأي."}
SAY_VERDICT_TWINS = {"en": "You already own something very similar: {items}.",
                     "fr": "Tu as déjà une pièce très proche : {items}.",
                     "ar": "عندك ديجا حاجة تشبهلها برشا: {items}."}
ASK_HOW_SCORING = {
    "en": ["How do you score outfits?", "How does the app decide if an outfit is good?"],
    "fr": ["Comment tu notes les tenues ?", "Comment l'appli décide qu'une tenue est bonne ?"],
    "ar": ["كيفاش تعطي نوطة للبسات؟", "كيفاش التطبيقة تعرف اللبسة باهية؟"],
    "arabizi": ["kifech ta3ti note lel lebset?", "kifech el application ta3ref el lebsa behya?"],
}
SAY_HOW_SCORING = {   # {weights} = "style 40%, colours 30%..."; {good}
    "en": "Each outfit gets a score out of 100 from four parts: {weights}. An outfit is good from {good}/100. "
          "The DressMe team sets these weights.",
    "fr": "Chaque tenue a une note sur 100 faite de quatre parties : {weights}. Une tenue est bonne à partir de {good}/100. "
          "C'est l'équipe DressMe qui fixe ces poids.",
    "ar": "كل لبسة تاخو نوطة على 100 من أربعة حاجات: {weights}. اللبسة باهية من {good}/100. "
          "الفريق متاع DressMe هو إلي يحط هالأوزان.",
}

# ------------------------------------------------------------------ titles of listings (synthetic)
SHOP_SOURCES = ["exist", "hamadi_abid"]
CITIES = ["Tunis", "Sfax", "Sousse", "Ariana", "Bizerte", "Nabeul"]
