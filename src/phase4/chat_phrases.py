"""
Words and sentences used by src/phase4/build_chat_dataset.py to write the synthetic
conversations that fine-tune the local chat model, in English, French and
Tunisian Arabic (Darija, in Arabic script; user questions also in "Arabizi",
Latin letters with 3 / 7 / 9 for ع / ح / ق, as people text).

TEAM: this file is plain data. The Darija was written without a native check:
please fix any word that sounds wrong (a wrong word here is learned by the model).
Every template must keep its {slots}.

Nouns: (word, gender) with gender m / f / mp / fp (French plural nouns: tes
chaussures). Arabic non-human plurals take feminine adjectives, so they are f.
Colours: (masculine, feminine); French plurals add an "s" unless the word is
in FR_INVARIABLE.
"""

# ------------------------------------------------------------------ item words
SUB_WORDS = {
    #  sub_category: (English, (French, gender), (Arabic, gender))
    "shirt": ("shirt", ("chemise", "f"), ("سورية", "f")),
    "sweater": ("sweater", ("pull", "m"), ("سويتر", "m")),
    "sweatshirt": ("sweatshirt", ("sweat", "m"), ("سويت", "m")),
    "t-shirt": ("t-shirt", ("t-shirt", "m"), ("تيشرت", "m")),
    "top": ("top", ("haut", "m"), ("توب", "m")),
    "tunic": ("tunic", ("tunique", "f"), ("تونيك", "m")),
    "capris": ("cropped trousers", ("pantacourt", "m"), ("بونطاكور", "m")),
    "jeans": ("jeans", ("jean", "m"), ("دجين", "m")),
    "leggings": ("leggings", ("legging", "m"), ("ليقينغ", "m")),
    "shorts": ("shorts", ("short", "m"), ("شورط", "m")),
    "skirt": ("skirt", ("jupe", "f"), ("جيب", "f")),
    "track-pants": ("joggers", ("jogging", "m"), ("جوقينغ", "m")),
    "trousers": ("trousers", ("pantalon", "m"), ("سروال", "m")),
    "dress": ("dress", ("robe", "f"), ("روبة", "f")),
    "jumpsuit": ("jumpsuit", ("combinaison", "f"), ("كومبينيزون", "f")),
    "blazer": ("blazer", ("blazer", "m"), ("بلايزر", "m")),
    "cape": ("cape", ("cape", "f"), ("كاب", "f")),
    "cardigan": ("cardigan", ("gilet", "m"), ("جيلي", "m")),
    "coat": ("coat", ("manteau", "m"), ("مونطو", "m")),
    "jacket": ("jacket", ("veste", "f"), ("فيستة", "f")),
    "waistcoat": ("waistcoat", ("gilet sans manches", "m"), ("جيلي بلا كمام", "m")),
    "casual-shoes": ("shoes", ("chaussures", "fp"), ("صباط", "m")),
    "flats": ("ballet flats", ("ballerines", "fp"), ("بالرينة", "f")),
    "flip-flops": ("flip-flops", ("tongs", "fp"), ("شلاكة", "f")),
    "formal-shoes": ("smart shoes", ("chaussures habillées", "fp"), ("صباط كلاسيك", "m")),
    "heels": ("heels", ("talons", "mp"), ("صباط بالكعب", "m")),
    "sandals": ("sandals", ("sandales", "fp"), ("صندال", "f")),
    "sneakers": ("sneakers", ("baskets", "fp"), ("سبادري", "m")),
    "backpack": ("backpack", ("sac à dos", "m"), ("كرطابلة", "f")),
    "clutch": ("clutch", ("pochette", "f"), ("بوشيت", "f")),
    "duffel-bag": ("holdall", ("sac de voyage", "m"), ("صاك سفر", "m")),
    "handbag": ("handbag", ("sac à main", "m"), ("صاك", "m")),
    "laptop-bag": ("laptop bag", ("sacoche", "f"), ("صاك بورتابل", "m")),
    "messenger-bag": ("messenger bag", ("besace", "f"), ("صاك كتف", "m")),
    "waist-bag": ("bum bag", ("banane", "f"), ("صاك بانان", "m")),
    "belt": ("belt", ("ceinture", "f"), ("سنتور", "f")),
    "bracelet": ("bracelet", ("bracelet", "m"), ("براسلي", "m")),
    "brooch": ("brooch", ("broche", "f"), ("بروش", "f")),
    "cap": ("cap", ("casquette", "f"), ("كاسكيت", "f")),
    "cufflinks": ("cufflinks", ("boutons de manchette", "mp"), ("بوتون مونشات", "m")),
    "earrings": ("earrings", ("boucles d'oreilles", "fp"), ("بلالط", "m")),
    "glasses": ("glasses", ("lunettes", "fp"), ("مرايات", "f")),
    "gloves": ("gloves", ("gants", "mp"), ("قفازات", "f")),
    "hair-accessory": ("hair accessory", ("accessoire cheveux", "m"), ("أكسسوار شعر", "m")),
    "hat": ("hat", ("chapeau", "m"), ("شابو", "m")),
    "jewellery-set": ("jewellery set", ("parure", "f"), ("طقم مصوغ", "m")),
    "necklace": ("necklace", ("collier", "m"), ("سلسلة", "f")),
    "ring": ("ring", ("bague", "f"), ("خاتم", "m")),
    "scarf": ("scarf", ("écharpe", "f"), ("فولار", "m")),
    "sunglasses": ("sunglasses", ("lunettes de soleil", "fp"), ("مرايات شمس", "f")),
    "suspenders": ("braces", ("bretelles", "fp"), ("بروتال", "f")),
    "tie": ("tie", ("cravate", "f"), ("كرافات", "f")),
    "wallet": ("wallet", ("portefeuille", "m"), ("ستوش", "m")),
    "watch": ("watch", ("montre", "f"), ("منقالة", "f")),
    "swim-shorts": ("swim shorts", ("short de bain", "m"), ("شورط بحر", "m")),
    "swimsuit": ("swimsuit", ("maillot de bain", "m"), ("مايو", "m")),
    "jebba": ("jebba", ("jebba", "f"), ("جبة", "f")),
    "kaftan": ("kaftan", ("caftan", "m"), ("قفطان", "m")),
}

COLOUR_WORDS = {
    #  colour: (English, (French m, French f), (Arabic m, Arabic f))
    "black": ("black", ("noir", "noire"), ("أكحل", "كحلة")),
    "white": ("white", ("blanc", "blanche"), ("أبيض", "بيضاء")),
    "cream": ("cream", ("crème", "crème"), ("كريمي", "كريمية")),
    "grey": ("grey", ("gris", "grise"), ("رمادي", "رمادية")),
    "beige": ("beige", ("beige", "beige"), ("بيج", "بيج")),
    "brown": ("brown", ("marron", "marron"), ("ماروني", "مارونية")),
    "khaki": ("khaki", ("kaki", "kaki"), ("كاكي", "كاكي")),
    "red": ("red", ("rouge", "rouge"), ("أحمر", "حمراء")),
    "burgundy": ("burgundy", ("bordeaux", "bordeaux"), ("بوردو", "بوردو")),
    "pink": ("pink", ("rose", "rose"), ("روز", "روز")),
    "orange": ("orange", ("orange", "orange"), ("برتقالي", "برتقالية")),
    "yellow": ("yellow", ("jaune", "jaune"), ("أصفر", "صفراء")),
    "green": ("green", ("vert", "verte"), ("أخضر", "خضراء")),
    "olive": ("olive", ("vert olive", "vert olive"), ("زيتوني", "زيتونية")),
    "teal": ("teal", ("bleu canard", "bleu canard"), ("بترولي", "بترولية")),
    "navy": ("navy", ("bleu marine", "bleu marine"), ("بلو مارين", "بلو مارين")),
    "blue": ("blue", ("bleu", "bleue"), ("أزرق", "زرقاء")),
    "purple": ("purple", ("violet", "violette"), ("موف", "موف")),
    "gold": ("gold", ("doré", "dorée"), ("ذهبي", "ذهبية")),
    "silver": ("silver", ("argenté", "argentée"), ("فضي", "فضية")),
    "multicolour": ("multicoloured", ("multicolore", "multicolore"), ("ملوّن", "ملوّنة")),
}
FR_INVARIABLE = {"marron", "kaki", "bordeaux", "orange", "crème", "vert olive", "bleu canard",
                 "bleu marine"}

CATEGORY_WORDS = {   # plural, for "you have 3 tops"
    "top": {"en": "tops", "fr": "hauts", "ar": "توبات"},
    "bottom": {"en": "bottoms", "fr": "bas", "ar": "سراول"},
    "dress": {"en": "dresses", "fr": "robes", "ar": "روبات"},
    "outerwear": {"en": "jackets and coats", "fr": "vestes et manteaux", "ar": "فيستات"},
    "shoes": {"en": "shoes", "fr": "chaussures", "ar": "صبابط"},
    "bag": {"en": "bags", "fr": "sacs", "ar": "صاكات"},
    "accessory": {"en": "accessories", "fr": "accessoires", "ar": "أكسسوارات"},
    "traditional": {"en": "traditional pieces", "fr": "tenues traditionnelles", "ar": "لبسة تقليدية"},
    "swimwear": {"en": "swimwear", "fr": "maillots", "ar": "مايوات"},
}

# how a user names a category in a question ("what shoes do I have?")
CATEGORY_ASK = {
    "top": {"en": "tops", "fr": "hauts", "ar": "توبات", "arabizi": "top"},
    "bottom": {"en": "trousers and skirts", "fr": "pantalons et jupes", "ar": "سراول", "arabizi": "sraweel"},
    "dress": {"en": "dresses", "fr": "robes", "ar": "روبات", "arabizi": "robet"},
    "outerwear": {"en": "jackets", "fr": "vestes", "ar": "فيستات", "arabizi": "vestet"},
    "shoes": {"en": "shoes", "fr": "chaussures", "ar": "صبابط", "arabizi": "sbabet"},
    "bag": {"en": "bags", "fr": "sacs", "ar": "صاكات", "arabizi": "sakat"},
    "accessory": {"en": "accessories", "fr": "accessoires", "ar": "أكسسوارات", "arabizi": "accessoires"},
}

SEASON_ASK = {   # "for {season}"
    "summer": {"en": "summer", "fr": "l'été", "ar": "الصيف", "arabizi": "sif"},
    "winter": {"en": "winter", "fr": "l'hiver", "ar": "الشتاء", "arabizi": "chta"},
    "mid-season": {"en": "spring", "fr": "la mi-saison", "ar": "الربيع", "arabizi": "rbi3"},
}
OCCASION_ASK = {   # "an outfit {occasion}"
    "casual": {"en": "for a normal day out", "fr": "pour une journée tranquille",
               "ar": "عادية للخرجة", "arabizi": "3adia lel khorja"},
    "formal": {"en": "for a formal event", "fr": "pour un événement habillé",
               "ar": "لمناسبة رسمية", "arabizi": "l'occasion rasmia"},
    "sport": {"en": "for the gym", "fr": "pour le sport", "ar": "للسبور", "arabizi": "lel sport"},
    "wedding": {"en": "for a wedding", "fr": "pour un mariage", "ar": "للعرس", "arabizi": "lel 3ers"},
    "eid": {"en": "for Eid", "fr": "pour l'Aïd", "ar": "للعيد", "arabizi": "lel 3id"},
    "work": {"en": "for work", "fr": "pour le travail", "ar": "للخدمة", "arabizi": "lel khedma"},
}

# ------------------------------------------------------------------ user questions
# arabizi questions are answered in Darija (Arabic script)
ASK_LIST = {
    "en": ["What's in my wardrobe?", "What clothes do I have?", "Can you list my clothes?",
           "Remind me what I own"],
    "fr": ["Qu'est-ce que j'ai dans ma garde-robe ?", "Montre-moi mes vêtements",
           "J'ai quoi comme habits ?", "Tu peux lister mes vêtements ?"],
    "ar": ["شنوة عندي في الخزانة؟", "وريني الحوايج متاعي", "شنوة عندي من حوايج؟"],
    "arabizi": ["chnowa 3andi fel khzena?", "warini 7wayji", "chnowa 3andi men 7wayej?"],
}
ASK_LIST_CATEGORY = {
    "en": ["What {cat} do I have?", "Show me my {cat}", "Which {cat} are in my wardrobe?"],
    "fr": ["J'ai quoi comme {cat} ?", "Montre-moi mes {cat}", "Quels {cat} j'ai ?"],
    "ar": ["شنوة عندي من {cat}؟", "وريني ال{cat} متاعي"],
    "arabizi": ["chnowa 3andi men {cat}?", "warini el {cat} mte3i"],
}
ASK_SUGGEST = {
    "en": ["What should I wear today?", "Pick an outfit for me", "Any outfit idea?",
           "I don't know what to wear, help me"],
    "fr": ["Je mets quoi aujourd'hui ?", "Choisis-moi une tenue", "Une idée de tenue ?",
           "Je sais pas quoi mettre, aide-moi"],
    "ar": ["شنوة نلبس اليوم؟", "اختارلي لبسة", "عندك فكرة لبسة؟", "ما نعرفش شنوة نلبس، عاوني"],
    "arabizi": ["chnowa nelbes lyoum?", "5tarli lebsa", "3andek fekra lebsa?",
                "ma na3rech chnowa nelbes, 3awenni"],
}
ASK_SUGGEST_OCCASION = {
    "en": ["What can I wear {occasion}?", "I need an outfit {occasion}", "Outfit idea {occasion}?"],
    "fr": ["Je mets quoi {occasion} ?", "Il me faut une tenue {occasion}", "Une tenue {occasion} ?"],
    "ar": ["شنوة نلبس {occasion}؟", "نحب لبسة {occasion}", "عطيني لبسة {occasion}"],
    "arabizi": ["chnowa nelbes {occasion}?", "n7eb lebsa {occasion}", "3tini lebsa {occasion}"],
}
ASK_SUGGEST_SEASON = {
    "en": ["What can I wear in {season}?", "Outfit ideas for {season}?"],
    "fr": ["Je mets quoi en {season} ?", "Des idées de tenues pour {season} ?"],
    "ar": ["شنوة نلبس في {season}؟", "عطيني أفكار لبسات متاع {season}"],
    "arabizi": ["chnowa nelbes fel {season}?", "3tini afkar lebset mta3 el {season}"],
}
ASK_SUGGEST_N = {   # n outfits
    "en": ["Give me {n} outfit ideas", "Suggest {n} outfits"],
    "fr": ["Donne-moi {n} idées de tenues", "Propose-moi {n} tenues"],
    "ar": ["عطيني {n} أفكار لبسات", "اقترحلي {n} لبسات"],
    "arabizi": ["3tini {n} afkar lebset", "e9tara7li {n} lebset"],
}
ASK_SCORE = {   # does A go with B? ({a}, {b} = "my black jeans", "ma jupe noire", "الدجين الكحل")
    "en": ["Does {a} go with {b}?", "Can I wear {a} with {b}?", "Is {a} with {b} a good match?"],
    "fr": ["{a} va avec {b} ?", "Je peux mettre {a} avec {b} ?", "{a} avec {b}, ça passe ?"],
    "ar": ["{a} يمشي مع {b}؟", "نجم نلبس {a} مع {b}؟", "{a} مع {b}، باهي؟"],
}
ASK_BUY = {
    "en": ["Should I buy this?", "I just scanned something, is it worth buying?",
           "Is the piece I scanned a good buy?"],
    "fr": ["Je l'achète ou pas ?", "J'ai scanné une pièce, ça vaut le coup ?",
           "La pièce que je viens de scanner, je la prends ?"],
    "ar": ["نشريه ولا لا؟", "تو صورت حاجة، تستاهل نشريها؟", "الحاجة إلي صورتها، نخوذها؟"],
    "arabizi": ["nechrih walla le?", "taw sawart 7aja, testehel nechriha?", "na5ouha walla le?"],
}
ASK_MORE = {   # follow-up after a suggestion
    "en": ["Another one?", "Something else?", "Give me more options"],
    "fr": ["Une autre ?", "Autre chose ?", "Donne-moi d'autres idées"],
    "ar": ["وحدة أخرى؟", "حاجة أخرى؟", "عطيني أفكار أخرى"],
    "arabizi": ["we7da o5ra?", "7aja o5ra?", "3tini afkar o5rin"],
}
ASK_HELLO = {
    "en": ["Hi!", "Hello", "Hey, what can you do?"],
    "fr": ["Salut !", "Bonjour", "Coucou, tu sers à quoi ?"],
    "ar": ["عسلامة!", "أهلا", "شنوة تنجم تعمل؟"],
    "arabizi": ["3aslema!", "ahla", "chnowa tnajem ta3mel?"],
}
ASK_THANKS = {
    "en": ["Thanks!", "Thank you, that helps"],
    "fr": ["Merci !", "Merci beaucoup, ça m'aide"],
    "ar": ["يعيشك!", "بارك الله فيك"],
    "arabizi": ["y3aychek!", "merci barcha"],
}
ASK_OFF_TOPIC = {
    "en": ["Can you help me with my maths homework?", "Who will win the match tonight?",
           "Write me a poem about the sea"],
    "fr": ["Tu peux m'aider pour mon devoir de maths ?", "Qui va gagner le match ce soir ?",
           "Écris-moi un poème sur la mer"],
    "ar": ["تنجم تعاوني في الدرس متاع الماط؟", "شكون باش يربح الماتش الليلة؟"],
    "arabizi": ["tnajem t3aweni fel devoir mta3 el math?", "chkoun bech yerba7 el match elila?"],
}

# ------------------------------------------------------------------ answers
SAY_HELLO = {
    "en": "Hi! I can pick an outfit from your wardrobe, tell you if two pieces go together, "
          "or help you decide if a piece you scanned is worth buying. What do you need?",
    "fr": "Salut ! Je peux te choisir une tenue dans ta garde-robe, te dire si deux pièces "
          "vont ensemble, ou t'aider à décider si une pièce scannée vaut le coup. Je t'écoute !",
    "ar": "عسلامة! نجم نختارلك لبسة من الخزانة متاعك، نقلك زوز حوايج يمشيو مع بعضهم ولا لا، "
          "ولا نعاونك تقرر إذا الحاجة إلي صورتها تستاهل تشريها. شنوة تحب؟",
}
SAY_THANKS = {
    "en": ["You're welcome! Have a great day.", "Anytime! Enjoy your outfit."],
    "fr": ["Avec plaisir ! Bonne journée.", "De rien ! Profite bien de ta tenue."],
    "ar": ["بالسلامة! نهارك زين.", "مرحبا بيك ديما! تتهنى باللبسة."],
}
SAY_OFF_TOPIC = {
    "en": "Sorry, I can only help with clothes: outfits, your wardrobe and what to buy. "
          "Want an outfit idea for today?",
    "fr": "Désolé, je ne peux t'aider que pour les vêtements : tenues, garde-robe et achats. "
          "Tu veux une idée de tenue pour aujourd'hui ?",
    "ar": "سامحني، نجم نعاونك كان في الحوايج: اللبسات، الخزانة متاعك وشنوة تشري. تحب فكرة لبسة لليوم؟",
}

SAY_LIST = {   # {n} pieces, {groups} = "tops: white t-shirt, ...; shoes: ..."
    "en": ["You have {n} pieces: {groups}.", "Here is what you own ({n} pieces): {groups}."],
    "fr": ["Tu as {n} pièces : {groups}.", "Voici ce que tu as ({n} pièces) : {groups}."],
    "ar": ["عندك {n} حوايج: {groups}.", "هاذا شنوة عندك ({n} حوايج): {groups}."],
}
SAY_LIST_CATEGORY = {
    "en": ["Your {cat}: {items}.", "You have {n} {cat}: {items}."],
    "fr": ["Tes {cat} : {items}.", "Tu as {n} {cat} : {items}."],
    "ar": ["ال{cat} متاعك: {items}.", "عندك {n} {cat}: {items}."],
}
SAY_LIST_EMPTY = {
    "en": "Your wardrobe is empty for now. Add your clothes in the Wardrobe tab (one photo each) and I can start suggesting outfits.",
    "fr": "Ta garde-robe est vide pour l'instant. Ajoute tes vêtements dans l'onglet Garde-robe (une photo par pièce) et je pourrai te proposer des tenues.",
    "ar": "الخزانة متاعك فارغة توا. زيد حوايجك في الخانة متاع الخزانة (تصويرة لكل حاجة) ونبداو نقترحو لبسات.",
}
SAY_LIST_CATEGORY_EMPTY = {
    "en": "You don't have any {cat} in your wardrobe yet.",
    "fr": "Tu n'as pas encore de {cat} dans ta garde-robe.",
    "ar": "ما عندكش {cat} في الخزانة متاعك توا.",
}

SAY_SUGGEST = {   # {items}, {score}
    "en": ["My best pick: {items} ({score}/100).", "Try {items}: it scores {score}/100.",
           "I'd go with {items} ({score}/100)."],
    "fr": ["Mon meilleur choix : {items} ({score}/100).", "Essaie {items} : ça fait {score}/100.",
           "Je partirais sur {items} ({score}/100)."],
    "ar": ["أحسن اختيار: {items} ({score}/100).", "جرب {items}: تاخو {score}/100.",
           "أنا نمشي على {items} ({score}/100)."],
}
SAY_SUGGEST_OCCASION = {
    "en": ["{Occasion}, my best pick is {items} ({score}/100)."],
    "fr": ["{Occasion}, mon meilleur choix : {items} ({score}/100)."],
    "ar": ["{Occasion}، أحسن اختيار هو {items} ({score}/100)."],
}
SAY_ANOTHER = {
    "en": ["Another option: {items} ({score}/100).", "Or: {items} ({score}/100)."],
    "fr": ["Autre option : {items} ({score}/100).", "Sinon : {items} ({score}/100)."],
    "ar": ["اختيار آخر: {items} ({score}/100).", "ولا: {items} ({score}/100)."],
}
SAY_GOOD_COLOURS = {
    "en": "The colours go well together.", "fr": "Les couleurs vont bien ensemble.",
    "ar": "الألوان يمشيو مع بعضهم.",
}
SAY_NOTE = {"en": "Note: {reasons}.", "fr": "Attention : {reasons}.", "ar": "ملاحظة: {reasons}."}
SAY_SUGGEST_EMPTY = {
    "en": "I can't build an outfit {occasion} from your wardrobe yet: {why}.",
    "fr": "Je ne peux pas encore composer de tenue {occasion} avec ta garde-robe : {why}.",
    "ar": "ما نجمتش نركب لبسة {occasion} من الخزانة متاعك: {why}.",
}
WHY_NO_CORE = {
    "en": "you need a top and a bottom, or a dress. Add them in the Wardrobe tab",
    "fr": "il faut un haut et un bas, ou une robe. Ajoute-les dans l'onglet Garde-robe",
    "ar": "لازمك توب وسروال، ولا روبة. زيدهم في الخانة متاع الخزانة",
}
WHY_FILTERED = {
    "en": "none of your pieces is marked for that (you can change the season and occasion of each piece in the Wardrobe tab)",
    "fr": "aucune de tes pièces n'est marquée pour ça (tu peux changer la saison et l'occasion de chaque pièce dans l'onglet Garde-robe)",
    "ar": "حتى حاجة من حوايجك ما هي مسجلة لهالشي (تنجم تبدل الموسم والمناسبة متاع كل حاجة في الخانة متاع الخزانة)",
}
SAY_NO_MORE = {
    "en": "That's all I can make with your wardrobe for now. One more top or bottom would open up new combinations.",
    "fr": "C'est tout ce que je peux composer avec ta garde-robe pour l'instant. Un haut ou un bas de plus ouvrirait de nouvelles combinaisons.",
    "ar": "هاذا الكل إلي نجم نركبو من الخزانة متاعك توا. توب ولا سروال زايد يحلّو برشا لبسات جداد.",
}
SAY_ASK_MORE = {
    "en": ["Want another idea?", ""], "fr": ["Tu veux une autre idée ?", ""],
    "ar": ["تحب فكرة أخرى؟", ""],
}

SAY_SCORE = {   # {items}, {score}, {judgement}
    "en": ["{items}: {score}/100. {judgement}", "Together, {items} get {score}/100. {judgement}"],
    "fr": ["{items} : {score}/100. {judgement}", "Ensemble, {items} font {score}/100. {judgement}"],
    "ar": ["{items}: {score}/100. {judgement}", "مع بعضهم، {items} ياخذو {score}/100. {judgement}"],
}
JUDGE_GOOD = {"en": "That works well!", "fr": "Ça marche bien !", "ar": "يمشيو مزيان!"}
JUDGE_OK = {"en": "That's fine.", "fr": "Ça passe.", "ar": "باهي."}
JUDGE_BAD = {"en": "Not the best match.", "fr": "Ce n'est pas l'idéal.", "ar": "موش أحسن حاجة."}
SAY_ADD_SHOES = {"en": "Add shoes to finish the look.", "fr": "Ajoute des chaussures pour finir la tenue.",
                 "ar": "زيد صباط باش تكمل اللبسة."}
SAY_CLASH = {
    "en": "You can't wear {items} at the same time ({reasons}): choose one of them.",
    "fr": "Tu ne peux pas porter {items} en même temps ({reasons}) : choisis-en un.",
    "ar": "ما تنجمش تلبس {items} في نفس الوقت ({reasons}): اختار واحد.",
}
SAY_NOT_OWNED = {
    "en": "I can't find {missing} in your wardrobe. {alternatives}",
    "fr": "Je ne trouve pas {missing} dans ta garde-robe. {alternatives}",
    "ar": "ما لقيتش {missing} في الخزانة متاعك. {alternatives}",
}
SAY_ALTERNATIVES = {
    "en": "Your {cat}: {items}. Want me to try one of them?",
    "fr": "Tes {cat} : {items}. Tu veux que j'en essaie un ?",
    "ar": "ال{cat} متاعك: {items}. تحب نجرب واحد منهم؟",
}
SAY_NO_ALTERNATIVE = {
    "en": "You have no {cat} at all for now.", "fr": "Tu n'as aucun {cat} pour l'instant.",
    "ar": "ما عندك حتى {cat} توا.",
}

SAY_BUY = {   # {item}, {n} good outfits, {example}
    "buy": {
        "en": "Go for it: {item} makes {n} good outfits with what you own, for example {example}.",
        "fr": "Fonce : {item} fait {n} bonnes tenues avec ce que tu as, par exemple {example}.",
        "ar": "اشريها: {item} تعمل {n} لبسات باهيين مع حوايجك، مثلا {example}.",
    },
    "think": {
        "en": "Think about it: {item} only makes {n} good outfit(s) with your wardrobe, like {example}. Friperie pieces can rarely be returned.",
        "fr": "Réfléchis bien : {item} ne fait que {n} bonne(s) tenue(s) avec ta garde-robe, comme {example}. En friperie, on peut rarement rendre une pièce.",
        "ar": "خمم مليح: {item} تعمل كان {n} لبسة باهية مع حوايجك، كيما {example}. حوايج الفريب نادرا ما ترجع.",
    },
    "skip": {
        "en": "I'd skip it: {item} doesn't add a good outfit to your wardrobe. Better keep your budget for something you'll wear more.",
        "fr": "Je passerais mon tour : {item} n'ajoute pas de bonne tenue à ta garde-robe. Garde ton budget pour une pièce que tu porteras plus.",
        "ar": "نخليها: {item} ما تزيد حتى لبسة باهية للخزانة متاعك. خلي فلوسك لحاجة تلبسها أكثر.",
    },
}
SAY_BUY_NO_SCAN = {
    "en": "I don't see any scanned piece from the last 24 hours. Take a photo of it in the Scan tab, then ask me again.",
    "fr": "Je ne vois aucune pièce scannée ces dernières 24 heures. Prends-la en photo dans l'onglet Scanner, puis redemande-moi.",
    "ar": "ما نشوف حتى حاجة مصورة في 24 ساعة إلي فاتو. صورها في الخانة متاع السكان، ومبعد عاود اسألني.",
}

# ------------------------------------------------------------------ the formula's reasons
# src/phase4/compatibility.py writes its reasons in English; (regex, fr, ar) for each.
# {0}, {1}... are the regex groups, translated with WORD_IN_REASON when known.
REASONS = [
    (r"the pieces have quite different styles", "les pièces ont des styles assez différents",
     "الحوايج ستيلهم مختلف برشا"),
    (r"(\w+) and (\w+) clash", "le {0} et le {1} ne vont pas ensemble", "{0} و{1} ما يمشيوش مع بعضهم"),
    (r"many bold colours \((.+)\)", "beaucoup de couleurs vives ({0})", "برشا ألوان قوية ({0})"),
    (r"two bold patterns \((\w+) \+ (\w+)\)", "deux motifs chargés ({0} + {1})", "زوز موتيفات قويين ({0} + {1})"),
    (r"no shoes", "pas de chaussures", "ما فماش صباط"),
    (r"missing a top or a bottom", "il manque un haut ou un bas", "ناقص توب ولا سروال"),
    (r"no main piece", "pas de pièce principale", "ما فماش حاجة أساسية"),
    (r"a full piece and a bottom together", "une pièce entière avec un bas", "روبة مع سروال"),
    (r"(\d+) items of ([\w-]+) \(max (\d+)\)", "{0} pièces de type {1} (max {2})", "{0} حوايج من نوع {1} (الأقصى {2})"),
    (r"(\d+) items of ([\w-]+)", "{0} pièces de type {1}", "{0} حوايج من نوع {1}"),
    (r"you already own (\d+) very similar (\w+) item\(s\)", "tu as déjà {0} pièce(s) très proche(s)",
     "عندك ديجا {0} حاجة تشبهلها برشا"),
    (r"coverage (\d) is below your level (\d)", "elle couvre moins que ton niveau ({0} < {1})",
     "تغطي أقل من المستوى متاعك ({0} < {1})"),
    (r"not for ([\w-]+)", "pas pour {0}", "موش ل{0}"),
]
# words inside a reason (colours use COLOUR_WORDS, sub-categories SUB_WORDS)
REASON_WORDS = {
    "fr": {"solid": "uni", "striped": "rayé", "checked": "carreaux", "floral": "fleuri",
           "printed": "imprimé", "summer": "l'été", "winter": "l'hiver", "mid-season": "la mi-saison",
           "casual": "tous les jours", "formal": "les occasions habillées", "sport": "le sport",
           "wedding": "un mariage", "eid": "l'Aïd", "work": "le travail", "top": "haut",
           "bottom": "bas", "dress": "robe", "outerwear": "veste", "shoes": "chaussures",
           "bag": "sac", "accessory": "accessoire", "traditional": "tenue traditionnelle",
           "swimwear": "maillot"},
    "ar": {"solid": "سادة", "striped": "مخطط", "checked": "كاروه", "floral": "ورود",
           "printed": "مطبوع", "summer": "الصيف", "winter": "الشتاء", "mid-season": "الربيع",
           "casual": "كل نهار", "formal": "المناسبات الرسمية", "sport": "السبور", "wedding": "العرس",
           "eid": "العيد", "work": "الخدمة", "top": "توب", "bottom": "سروال", "dress": "روبة",
           "outerwear": "فيستة", "shoes": "صباط", "bag": "صاك", "accessory": "أكسسوار",
           "traditional": "لبسة تقليدية", "swimwear": "مايو"},
}
