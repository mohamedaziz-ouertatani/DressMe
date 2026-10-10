# Darija review sheet (src/phase4/chat_phrases.py, chat_phrases_agents.py)

Every Darija word and sentence the chat dataset uses, for a native speaker to check. The fine-tuned model learns each one **exactly as written**, so a wrong word here becomes a wrong word in the app.

How to use: write the right version in the **Correction** column (leave it empty if it is fine). Keep the `{slots}` (they are filled in automatically). The **Key** column says where the text lives in `src/phase4/chat_phrases.py`. The transliteration and meaning were written by Claude, not by a native speaker, so they can be wrong too. The **Note** column holds Claude's own doubts, as questions only: the native speaker decides.

General points to decide once:

| # | Question | Correction |
|---|---|---|
| G1 | Feminine colours are written MSA-style with ـاء (بيضاء، حمراء، صفراء، خضراء، زرقاء، الشتاء). Should they be بيضا، حمرا، صفرا، خضرا، زرقا، الشتا? | |
| G2 | "that / which" is spelled إلي everywhere. Should it be اللي? | |
| G3 | Code rule: the verb in "{a} يمشي مع {b}؟" is always masculine, e.g. "السورية الكحلة يمشي مع التونيك الأزرق؟". Should it become تمشي when {a} is feminine? | |
| G4 | Code rule: nouns of two words never get "ال", e.g. "الجوقينغ البلو مارين يمشي مع صباط كلاسيك زيتوني؟". How should "the smart shoes" be said: الصباط الكلاسيك? | |
| G5 | Code rule: colours follow the noun's gender (fem. noun → fem. colour, "سورية كحلة"). Plural-looking words (صباط، نظارات) are treated as one item. Is that right? | |
| G6 | "اشريها / نخليها / تعمل" in the buy advice are always feminine ("it" = الحاجة), even when the item is masculine (الدجين). OK because it refers to "الحاجة", or should it follow the item? | |

Examples of full questions the dataset builds (from the test split):

- السورية الكحلة يمشي مع التونيك الأزرق؟
- الليقينغ الأحمر مع السبادري البيج، باهي؟
- نجم نلبس الجوقينغ الكحل مع الصباط الكحل؟
- الجوقينغ البلو مارين يمشي مع صباط كلاسيك زيتوني؟
- عطيني لبسة للعرس / نحب لبسة للسبور / شنوة عندي من صبابط؟

## 1. Clothes (SUB_WORDS: word, gender)

| Key | Arabic | Transliteration | Meaning | Note | Correction |
|---|---|---|---|---|---|
| shirt | سورية (f) | sourya | shirt | | |
| sweater | تريكو (m) | triko | sweater, knit | | سويتر |
| sweatshirt | سويت (m) | swit | sweatshirt | | |
| t-shirt | تيشرت (m) | tishirt | t-shirt | | |
| top | توب (m) | top | top | | |
| tunic | تونيك (m) | tunik | tunic | masculine here, feminine in French: right? | |
| capris | بونطاكور (m) | bontakour | cropped trousers | | |
| jeans | دجين (m) | djin | jeans | | |
| leggings | ليقينغ (m) | liging | leggings | spelling? | |
| shorts | شورط (m) | short | shorts | | |
| skirt | جيبة (f) | jiba | skirt | | جيب |
| track-pants | جوقينغ (m) | joging | joggers / track pants | | |
| trousers | سروال (m) | serwel | trousers | | |
| dress | روبة (f) | roba | dress | | |
| jumpsuit | كومبينيزون (f) | kombinizon | jumpsuit | | |
| blazer | بلايزر (m) | blayzer | blazer | | |
| cape | كاب (f) | kap | cape | | |
| cardigan | جيلي (m) | jili | cardigan | | |
| coat | مونطو (m) | monto | coat | | |
| jacket | فيستة (f) | vista | jacket | | |
| waistcoat | جيلي بلا كمام (m) | jili bla kmam | sleeveless gilet | | |
| casual-shoes | صباط (m) | sabbat | shoes | | |
| flats | بالرينة (f) | balerina | ballet flats | | |
| flip-flops | شلاكة (f) | shlaka | flip-flops | | |
| formal-shoes | صباط كلاسيك (m) | sabbat klasik | smart shoes | | |
| heels | صباط بالكعب (m) | sabbat bel ka3b | heels | | |
| sandals | صندالة (f) | sandala | sandals | | صندال |
| sneakers | سبادري (m) | sbadri | sneakers | | |
| backpack | كرطابلة (f) | kartabla | backpack (school bag) | | |
| clutch | بوشيت (f) | pochette | clutch bag | | |
| duffel-bag | صاك سفر (m) | sak safar | travel bag | | |
| handbag | صاك (m) | sak | handbag | | |
| laptop-bag | صاك بورتابل (m) | sak portabl | laptop bag | | |
| messenger-bag | صاك كتف (m) | sak ktef | shoulder bag | | |
| waist-bag | صاك بانان (m) | sak banan | bum bag | | |
| belt | سنتورة (f) | sentoura | belt | | سنتور |
| bracelet | سوار (m) | swar | bracelet | | براسلي |
| brooch | بروش (f) | broch | brooch | | |
| cap | كاسكيت (f) | kasket | cap | | |
| cufflinks | بوتون مونشات (m) | bouton monshet | cufflinks | | |
| earrings | حلق (m) | 7la9 | earrings | the word people use? | بلالط |
| glasses | نظارات (f) | nadharat | glasses | MSA? (مرايات?) | مرايات |
| gloves | قفازات (f) | 9affazat | gloves | MSA? | |
| hair-accessory | أكسسوار شعر (m) | aksesouar sh3ar | hair accessory | | |
| hat | شابو (m) | shapo | hat | | |
| jewellery-set | طقم مصوغ (m) | ta9m masough | jewellery set | | |
| necklace | عقد (m) | 3e9d | necklace | MSA? (سلسلة / كوليي?) | سلسلة |
| ring | خاتم (m) | 5atem | ring | | |
| scarf | فولار (m) | foular | scarf | | |
| sunglasses | نظارات شمس (f) | nadharat shams | sunglasses | same as glasses | مرايات شمس |
| suspenders | بروتال (f) | bretal | braces | | |
| tie | كرافات (f) | kravat | tie | | |
| wallet | بزطام (m) | bezdam | wallet | | ستوش |
| watch | مونتر (f) | montr | watch | | منقالة |
| swim-shorts | شورط بحر (m) | short b7ar | swim shorts | | |
| swimsuit | مايو (m) | mayo | swimsuit | | |
| jebba | جبة (f) | jebba | jebba | | |
| kaftan | قفطان (m) | 9eftan | kaftan | | |

## 2. Colours (COLOUR_WORDS: masculine / feminine)

| Key | Arabic m | Arabic f | Transliteration | Meaning | Note | Correction |
|---|---|---|---|---|---|---|
| black | كحل | كحلة | ka7el / ka7la | black | | أكحل |
| white | أبيض | بيضاء | abyedh / bidha | white | G1 | |
| cream | كريمي | كريمية | krimi / krimiya | cream | | |
| grey | رمادي | رمادية | rmedi / rmediya | grey | | |
| beige | بيج | بيج | bej | beige | | |
| brown | ماروني | مارونية | marroni / marroniya | brown | | |
| khaki | كاكي | كاكي | kaki | khaki | | |
| red | أحمر | حمراء | a7mer / 7amra | red | G1 | |
| burgundy | بوردو | بوردو | bordo | burgundy | | |
| pink | روز | روز | roz | pink | | |
| orange | برتقالي | برتقالية | bourtou9ali / bourtou9aliya | orange | the word people use (بردڨاني?) | |
| yellow | أصفر | صفراء | asfer / safra | yellow | G1 | |
| green | أخضر | خضراء | a5dhar / 5adhra | green | G1 | |
| olive | زيتوني | زيتونية | zitouni / zitouniya | olive | | |
| teal | بترولي | بترولية | petroli / petroliya | teal (petrol blue) | | |
| navy | بلو مارين | بلو مارين | blou marin | navy | | |
| blue | أزرق | زرقاء | azra9 / zar9a | blue | G1 | |
| purple | موف | موف | mov | purple (mauve) | | |
| gold | ذهبي | ذهبية | dhahbi / dhahbiya | gold | | |
| silver | فضي | فضية | fedhi / fedhiya | silver | | |
| multicolour | ملوّن | ملوّنة | mlawwen / mlawna | multicoloured | | |

## 3. Category, season and occasion words

| Key | Arabic | Transliteration | Meaning | Correction |
|---|---|---|---|---|
| CATEGORY_WORDS top / CATEGORY_ASK top | توبات | topet | tops | |
| bottom | سراول | sraweel | trousers, bottoms | |
| dress | روبات | robet | dresses | |
| outerwear | فيستات | vistet | jackets | |
| shoes | صبابط | sbabet | shoes | |
| bag | صاكات | saket | bags | |
| accessory | أكسسوارات | aksesouarat | accessories | |
| traditional | لبسة تقليدية | lebsa ta9lidiya | traditional outfit(s) | |
| swimwear | مايوات | mayouet | swimsuits | |
| SEASON_ASK summer | الصيف | es-sif | summer | |
| SEASON_ASK winter | الشتاء | esh-shta | winter (G1) | |
| SEASON_ASK mid-season | الربيع | er-rbi3 | spring (used for mid-season) | |
| OCCASION_ASK casual | عادية للخرجة | 3adiya lel 5arja | an ordinary one, for going out | |
| OCCASION_ASK formal | لمناسبة رسمية | l-mounasba rasmiya | for a formal occasion | |
| OCCASION_ASK sport | للسبور | lel sport | for sport | |
| OCCASION_ASK wedding | للعرس | lel 3ors | for a wedding | |
| OCCASION_ASK eid | للعيد | lel 3id | for Eid | |
| OCCASION_ASK work | للخدمة | lel 5edma | for work | |

Arabizi versions (CATEGORY_ASK / SEASON_ASK / OCCASION_ASK): top, sraweel, robet, vestet, sbabet, sakat, accessoires; sif, chta, rbi3; 3adia lel khorja, l'occasion rasmia, lel sport, lel 3ers, lel 3id, lel khedma. Correction: ...

## 4. User questions (Arabic script, then Arabizi)

| Key | Arabic | Transliteration | Meaning | Note | Correction |
|---|---|---|---|---|---|
| ASK_LIST | شنوة عندي في الخزانة؟ | shnowa 3andi fel 5zena? | What do I have in the wardrobe? | | |
| ASK_LIST | وريني الحوايج متاعي | warrini el 7wayej mte3i | Show me my clothes | | |
| ASK_LIST | شنوة عندي من حوايج؟ | shnowa 3andi men 7wayej? | What clothes do I have? | | |
| ASK_LIST_CATEGORY | شنوة عندي من {cat}؟ | shnowa 3andi men {cat}? | What {cat} do I have? | | |
| ASK_LIST_CATEGORY | وريني ال{cat} متاعي | warrini el{cat} mte3i | Show me my {cat} | | |
| ASK_SUGGEST | شنوة نلبس اليوم؟ | shnowa nelbes el-youm? | What should I wear today? | | |
| ASK_SUGGEST | اختارلي لبسة | e5tarli lebsa | Pick an outfit for me | | |
| ASK_SUGGEST | عندك فكرة لبسة؟ | 3andek fekra lebsa? | Do you have an outfit idea? | | |
| ASK_SUGGEST | ما نعرفش شنوة نلبس، عاوني | ma na3rafsh shnowa nelbes, 3awenni | I don't know what to wear, help me | | |
| ASK_SUGGEST_OCCASION | شنوة نلبس {occasion}؟ | shnowa nelbes {occasion}? | What do I wear {occasion}? | | |
| ASK_SUGGEST_OCCASION | نحب لبسة {occasion} | n7eb lebsa {occasion} | I want an outfit {occasion} | | |
| ASK_SUGGEST_OCCASION | عطيني لبسة {occasion} | a3tini lebsa {occasion} | Give me an outfit {occasion} | | |
| ASK_SUGGEST_SEASON | شنوة نلبس في {season}؟ | shnowa nelbes fi {season}? | What do I wear in {season}? | | |
| ASK_SUGGEST_SEASON | عطيني أفكار لبسات متاع {season} | a3tini afkar lebsat mta3 {season} | Give me outfit ideas for {season} | | |
| ASK_SUGGEST_N | عطيني {n} أفكار لبسات | a3tini {n} afkar lebsat | Give me {n} outfit ideas | | |
| ASK_SUGGEST_N | اقترحلي {n} لبسات | e9tera7li {n} lebsat | Suggest {n} outfits to me | | |
| ASK_SCORE | {a} يمشي مع {b}؟ | {a} yemshi m3a {b}? | Does {a} go with {b}? | G3 | |
| ASK_SCORE | نجم نلبس {a} مع {b}؟ | najjem nelbes {a} m3a {b}? | Can I wear {a} with {b}? | | |
| ASK_SCORE | {a} مع {b}، باهي؟ | {a} m3a {b}, behi? | {a} with {b}, is it good? | | |
| ASK_BUY | نشريه ولا لا؟ | neshrih walla le? | Should I buy it or not? | | |
| ASK_BUY | تو صورت حاجة، تستاهل نشريها؟ | taw sawwart 7aja, testehel neshriha? | I just took a photo of something, is it worth buying? | تو or توا? | |
| ASK_BUY | الحاجة إلي صورتها، نخوذها؟ | el 7aja elli sawwartha, n5ouha? | The thing I photographed, should I take it? | spelling of نخوذها? | |
| ASK_MORE | وحدة أخرى؟ | we7da o5ra? | Another one? | أخرى or أخرا? | |
| ASK_MORE | حاجة أخرى؟ | 7aja o5ra? | Something else? | | |
| ASK_MORE | عطيني أفكار أخرى | a3tini afkar o5ra | Give me other ideas | Arabizi version says "o5rin" | |
| ASK_HELLO | عسلامة! | 3aslema! | Hi! | | |
| ASK_HELLO | أهلا | ahla | Hello | | |
| ASK_HELLO | شنوة تنجم تعمل؟ | shnowa tnajjem ta3mel? | What can you do? | | |
| ASK_THANKS | يعيشك! | y3ayshek! | Thanks! | | |
| ASK_THANKS | بارك الله فيك | barak allahou fik | God bless you (thanks) | | |
| ASK_OFF_TOPIC | تنجم تعاوني في الدرس متاع الماط؟ | tnajjem t3aweni fel dars mta3 el math? | Can you help me with my maths lesson? | Arabizi version says "devoir" (homework) | |
| ASK_OFF_TOPIC | شكون باش يربح الماتش الليلة؟ | shkoun bash yerba7 el match ellila? | Who will win the match tonight? | | |

Arabizi questions (the model must answer these in Darija, Arabic script):

| Key | Arabizi | Meaning | Note | Correction |
|---|---|---|---|---|
| ASK_LIST | chnowa 3andi fel khzena? | What do I have in the wardrobe? | | |
| ASK_LIST | warini 7wayji | Show me my clothes | | |
| ASK_LIST | chnowa 3andi men 7wayej? | What clothes do I have? | | |
| ASK_LIST_CATEGORY | chnowa 3andi men {cat}? | What {cat} do I have? | | |
| ASK_LIST_CATEGORY | warini el {cat} mte3i | Show me my {cat} | | |
| ASK_SUGGEST | chnowa nelbes lyoum? | What should I wear today? | | |
| ASK_SUGGEST | 5tarli lebsa | Pick an outfit for me | | |
| ASK_SUGGEST | 3andek fekra lebsa? | Any outfit idea? | | |
| ASK_SUGGEST | ma na3rech chnowa nelbes, 3awenni | I don't know what to wear, help me | "na3rech": typo for "na3rafch"? | |
| ASK_SUGGEST_OCCASION | chnowa nelbes {occasion}? | What do I wear {occasion}? | | |
| ASK_SUGGEST_OCCASION | n7eb lebsa {occasion} | I want an outfit {occasion} | | |
| ASK_SUGGEST_OCCASION | 3tini lebsa {occasion} | Give me an outfit {occasion} | | |
| ASK_SUGGEST_SEASON | chnowa nelbes fel {season}? | What do I wear in {season}? | | |
| ASK_SUGGEST_SEASON | 3tini afkar lebset mta3 el {season} | Outfit ideas for {season} | | |
| ASK_SUGGEST_N | 3tini {n} afkar lebset | Give me {n} outfit ideas | | |
| ASK_SUGGEST_N | e9tara7li {n} lebset | Suggest {n} outfits | | |
| ASK_BUY | nechrih walla le? | Should I buy it or not? | | |
| ASK_BUY | taw sawart 7aja, testehel nechriha? | I just took a photo of something, worth buying? | | |
| ASK_BUY | na5ouha walla le? | Should I take it or not? | | |
| ASK_MORE | we7da o5ra? | Another one? | | |
| ASK_MORE | 7aja o5ra? | Something else? | | |
| ASK_MORE | 3tini afkar o5rin | Give me other ideas | | |
| ASK_HELLO | 3aslema! / ahla | Hi! / Hello | | |
| ASK_HELLO | chnowa tnajem ta3mel? | What can you do? | | |
| ASK_THANKS | y3aychek! / merci barcha | Thanks! / Thanks a lot | | |
| ASK_OFF_TOPIC | tnajem t3aweni fel devoir mta3 el math? | Can you help with my maths homework? | | |
| ASK_OFF_TOPIC | chkoun bech yerba7 el match elila? | Who will win the match tonight? | | |

## 5. Assistant answers

| Key | Arabic | Transliteration | Meaning | Note | Correction |
|---|---|---|---|---|---|
| SAY_HELLO | عسلامة! نجم نختارلك لبسة من الخزانة متاعك، نقلك زوز حوايج يمشيو مع بعضهم ولا لا، ولا نعاونك تقرر إذا الحاجة إلي صورتها تستاهل تشريها. شنوة تحب؟ | 3aslema! najjem ne5tarlek lebsa mel 5zena mte3ek, n9ollek zouz 7wayej yemshiw m3a ba3dhhom walla le, walla n3awnek t9arrer ken el 7aja elli sawwartha testehel teshriha. shnowa t7eb? | Hi! I can pick an outfit from your wardrobe, tell you if two pieces go together or not, or help you decide if the thing you photographed is worth buying. What would you like? | | |
| SAY_THANKS | بالسلامة! نهارك زين. | bessléma! nharek zin. | (lit. "goodbye / go safely!") Have a nice day. | بالسلامة means goodbye, not "you're welcome": intended? | |
| SAY_THANKS | مرحبا بيك ديما! تتهنى باللبسة. | mar7ba bik dima! tethanna bel lebsa. | You're always welcome! Enjoy the outfit. | | |
| SAY_OFF_TOPIC | سامحني، نجم نعاونك كان في الحوايج: اللبسات، الخزانة متاعك وشنوة تشري. تحب فكرة لبسة لليوم؟ | sam7ni, najjem n3awnek ken fel 7wayej: el lebsat, el 5zena mte3ek w shnowa teshri. t7eb fekra lebsa lel youm? | Sorry, I can only help with clothes: outfits, your wardrobe and what to buy. Want an outfit idea for today? | | |
| SAY_LIST | عندك {n} حوايج: {groups}. | 3andek {n} 7wayej: {groups}. | You have {n} pieces: {groups}. | | |
| SAY_LIST | هاذا شنوة عندك ({n} حوايج): {groups}. | hedha shnowa 3andek ({n} 7wayej): {groups}. | This is what you have ({n} pieces): {groups}. | | |
| SAY_LIST_CATEGORY | ال{cat} متاعك: {items}. | el{cat} mte3ek: {items}. | Your {cat}: {items}. | | |
| SAY_LIST_CATEGORY | عندك {n} {cat}: {items}. | 3andek {n} {cat}: {items}. | You have {n} {cat}: {items}. | | |
| SAY_LIST_EMPTY | الخزانة متاعك فارغة توا. زيد حوايجك في الخانة متاع الخزانة (تصويرة لكل حاجة) ونبداو نقترحو لبسات. | el 5zena mte3ek far8a tawa. zid 7wayjek fel 5ana mta3 el 5zena (taswira lkol 7aja) w nebdew ne9ter7ou lebsat. | Your wardrobe is empty for now. Add your clothes in the Wardrobe tab (one photo per piece) and we'll start suggesting outfits. | | |
| SAY_LIST_CATEGORY_EMPTY | ما عندكش {cat} في الخزانة متاعك توا. | ma 3andeksh {cat} fel 5zena mte3ek tawa. | You don't have any {cat} in your wardrobe yet. | | |
| SAY_SUGGEST | أحسن اختيار: {items} ({score}/100). | a7sen e5tiyar: {items} | Best choice: {items} | | |
| SAY_SUGGEST | جرب {items}: تاخو {score}/100. | jarreb {items}: te5ou {score}/100. | Try {items}: it gets {score}/100. | | |
| SAY_SUGGEST | أنا نمشي على {items} ({score}/100). | ana nemshi 3la {items} | I'd go for {items} | | |
| SAY_SUGGEST_OCCASION | {Occasion}، أحسن اختيار هو {items} ({score}/100). | {Occasion}, a7sen e5tiyar houwa {items} | {Occasion}, the best choice is {items} | | |
| SAY_ANOTHER | اختيار آخر: {items} ({score}/100). | e5tiyar e5er: {items} | Another option: {items} | | |
| SAY_ANOTHER | ولا: {items} ({score}/100). | walla: {items} | Or: {items} | | |
| SAY_GOOD_COLOURS | الألوان يمشيو مع بعضهم. | el alwen yemshiw m3a ba3dhhom. | The colours go together. | | |
| SAY_NOTE | ملاحظة: {reasons}. | mla7dha: {reasons}. | Note: {reasons}. | | |
| SAY_SUGGEST_EMPTY | ما نجمتش نركب لبسة {occasion} من الخزانة متاعك: {why}. | ma najjamtesh nrakkeb lebsa {occasion} mel 5zena mte3ek: {why}. | I couldn't put together an outfit {occasion} from your wardrobe: {why}. | | |
| WHY_NO_CORE | لازمك توب وسروال، ولا روبة. زيدهم في الخانة متاع الخزانة | lezmek top w serwel, walla roba. zidhom fel 5ana mta3 el 5zena | You need a top and trousers, or a dress. Add them in the Wardrobe tab | | |
| WHY_FILTERED | حتى حاجة من حوايجك ما هي مسجلة لهالشي (تنجم تبدل الموسم والمناسبة متاع كل حاجة في الخانة متاع الخزانة) | 7atta 7aja men 7wayjek ma hi msajla l-hal-shi (tnajjem tbaddel el mawsem wel mounasba mta3 kol 7aja fel 5ana mta3 el 5zena) | None of your pieces is marked for that (you can change the season and occasion of each piece in the Wardrobe tab) | | |
| SAY_NO_MORE | هاذا الكل إلي نجم نركبو من الخزانة متاعك توا. توب ولا سروال زايد يحلّو برشا لبسات جداد. | hedha el kol elli najjem nrakkbou mel 5zena mte3ek tawa. top walla serwel zayed y7allou barsha lebsat jdod. | That's all I can put together from your wardrobe now. One more top or trousers would open up lots of new outfits. | يحلّو (plural) with a singular subject? | |
| SAY_ASK_MORE | تحب فكرة أخرى؟ | t7eb fekra o5ra? | Want another idea? | | |
| SAY_SCORE | {items}: {score}/100. {judgement} | | | | |
| SAY_SCORE | مع بعضهم، {items} ياخذو {score}/100. {judgement} | m3a ba3dhhom, {items} ya5dhou {score}/100. | Together, {items} get {score}/100. | | |
| JUDGE_GOOD | يمشيو مزيان! | yemshiw mezyen! | They go well together! | مزيان sounds Moroccan / Algerian: باهي / مليح? | |
| JUDGE_OK | باهي. | behi. | It's fine. | | |
| JUDGE_BAD | موش أحسن حاجة. | mush a7sen 7aja. | Not the best thing. | | |
| SAY_ADD_SHOES | زيد صباط باش تكمل اللبسة. | zid sabbat bash tkammel el lebsa. | Add shoes to finish the outfit. | | |
| SAY_CLASH | ما تنجمش تلبس {items} في نفس الوقت ({reasons}): اختار واحد. | ma tnajjemsh telbes {items} fi nafs el wa9t ({reasons}): e5tar we7ed. | You can't wear {items} at the same time ({reasons}): choose one. | | |
| SAY_NOT_OWNED | ما لقيتش {missing} في الخزانة متاعك. {alternatives} | ma l9itesh {missing} fel 5zena mte3ek. | I didn't find {missing} in your wardrobe. | | |
| SAY_ALTERNATIVES | ال{cat} متاعك: {items}. تحب نجرب واحد منهم؟ | el{cat} mte3ek: {items}. t7eb njarreb we7ed menhom? | Your {cat}: {items}. Want me to try one of them? | | |
| SAY_NO_ALTERNATIVE | ما عندك حتى {cat} توا. | ma 3andek 7atta {cat} tawa. | You have no {cat} at all for now. | | |
| SAY_BUY buy | اشريها: {item} تعمل {n} لبسات باهيين مع حوايجك، مثلا {example}. | eshriha: {item} ta3mel {n} lebsat behyin m3a 7wayjek, mathalan {example}. | Buy it: {item} makes {n} good outfits with your clothes, for example {example}. | G6 | |
| SAY_BUY think | خمم مليح: {item} تعمل كان {n} لبسة باهية مع حوايجك، كيما {example}. حوايج الفريب نادرا ما ترجع. | 5ammem mli7: {item} ta3mel ken {n} lebsa behya m3a 7wayjek, kima {example}. 7wayej el frip nadiran ma traja3. | Think it over: {item} makes only {n} good outfit(s) with your clothes, like {example}. Friperie clothes can rarely be returned. | نادرا ما sounds MSA? | |
| SAY_BUY skip | نخليها: {item} ما تزيد حتى لبسة باهية للخزانة متاعك. خلي فلوسك لحاجة تلبسها أكثر. | n5alliha: {item} ma tzid 7atta lebsa behya lel 5zena mte3ek. 5alli flousek l-7aja telbesha akthar. | I'd leave it: {item} doesn't add any good outfit to your wardrobe. Keep your money for something you'll wear more. | G6 | |
| SAY_BUY_NO_SCAN | ما نشوف حتى حاجة مصورة في 24 ساعة إلي فاتو. صورها في الخانة متاع السكان، ومبعد عاود اسألني. | ma nshouf 7atta 7aja msawra fi 24 sa3a elli fetou. sawwarha fel 5ana mta3 el scan, w mba3d 3awed es2alni. | I don't see any photographed piece in the last 24 hours. Take a photo of it in the Scan tab, then ask me again. | | |

## 6. Reasons from the compatibility formula (REASONS)

| English reason | Arabic | Transliteration | Meaning | Correction |
|---|---|---|---|---|
| the pieces have quite different styles | الحوايج ستيلهم مختلف برشا | el 7wayej stilhom m5talef barsha | the pieces' styles are very different | |
| {0} and {1} clash | {0} و{1} ما يمشيوش مع بعضهم | {0} w {1} ma yemshiwsh m3a ba3dhhom | {0} and {1} don't go together | |
| many bold colours ({0}) | برشا ألوان قوية ({0}) | barsha alwen 9wiya | lots of strong colours | |
| two bold patterns ({0} + {1}) | زوز موتيفات قويين ({0} + {1}) | zouz motifet 9wiyin | two strong patterns | |
| no shoes | ما فماش صباط | ma fammesh sabbat | there are no shoes | |
| missing a top or a bottom | ناقص توب ولا سروال | na9es top walla serwel | a top or trousers is missing | |
| no main piece | ما فماش حاجة أساسية | ma fammesh 7aja asasiya | there is no main piece | |
| a full piece and a bottom together | روبة مع سروال | roba m3a serwel | a dress with trousers | |
| {0} items of {1} (max {2}) | {0} حوايج من نوع {1} (الأقصى {2}) | {0} 7wayej men nou3 {1} (el a9sa {2}) | {0} pieces of type {1} (maximum {2}) | |
| {0} items of {1} | {0} حوايج من نوع {1} | {0} 7wayej men nou3 {1} | {0} pieces of type {1} | |
| you already own {0} very similar item(s) | عندك ديجا {0} حاجة تشبهلها برشا | 3andek déjà {0} 7aja teshbehlha barsha | you already have {0} thing(s) very like it | |
| coverage {0} is below your level {1} | تغطي أقل من المستوى متاعك ({0} < {1}) | tghatti a9al mel mestwa mte3ek | it covers less than your level | |
| not for {0} | موش ل{0} | mush l{0} | not for {0} | |

Words inside reasons (REASON_WORDS ar):

| Key | Arabic | Transliteration | Meaning | Correction |
|---|---|---|---|---|
| solid | سادة | sada | plain (one colour) | |
| striped | مخطط | m5attat | striped | |
| checked | كاروه | karro | checked | |
| floral | ورود | wroud | flowers (floral) | |
| printed | مطبوع | matbou3 | printed | |
| summer | الصيف | es-sif | summer | |
| winter | الشتاء | esh-shta | winter (G1) | |
| mid-season | الربيع | er-rbi3 | spring | |
| casual | كل نهار | kol nhar | every day | |
| formal | المناسبات الرسمية | el mounasbet er-rasmiya | formal occasions | |
| sport | السبور | es-sport | sport | |
| wedding | العرس | el 3ors | the wedding | |
| eid | العيد | el 3id | Eid | |
| work | الخدمة | el 5edma | work | |
| top | توب | top | top | |
| bottom | سروال | serwel | trousers / bottom | |
| dress | روبة | roba | dress | |
| outerwear | فيستة | vista | jacket | |
| shoes | صباط | sabbat | shoes | |
| bag | صاك | sak | bag | |
| accessory | أكسسوار | aksesouar | accessory | |
| traditional | لبسة تقليدية | lebsa ta9lidiya | traditional outfit | |
| swimwear | مايو | mayo | swimsuit | |

## 7. New phrases for the agents (2026-10-08, NOT reviewed)

Written by Claude for the five agents' new scenarios (`src/phase4/chat_phrases_agents.py`), plus the
chat's fallback message (`NO_ANSWER` in `backend/app/routers/chat.py`). The model v2 (`dressme-chat-v2`) was
trained on them as written. **Meaning** is the English version of the same sentence (for FACTS: the English
fact it translates). No transliteration yet. Fix them in the Correction column, then rebuild the dataset.

| Key | Darija | Meaning | Correction |
|---|---|---|---|
| AGENT_NAMES.stylist | الستيليست | the Stylist | |
| AGENT_NAMES.shopping | مستشار الشراء | the Shopping advisor | |
| AGENT_NAMES.analyst | محلل الخزانة | the Wardrobe analyst | |
| AGENT_NAMES.seller | مساعد البيع | the Seller assistant | |
| AGENT_NAMES.explainer | المفسّر | the Explainer | |
| ASK_COMPLETE | شنوة يمشي مع {a}؟ | What goes with {a}? | |
| ASK_COMPLETE | كملي لبسة مع {a} | Complete an outfit around {a} | |
| ASK_COMPLETE | نحب نلبس {a}، شنوة نزيد؟ | I want to wear {a}, what do I add? | |
| ASK_HOW_SCORING | كيفاش تعطي نوطة للبسات؟ | How do you score outfits? | |
| ASK_HOW_SCORING | كيفاش التطبيقة تعرف اللبسة باهية؟ | How does the app decide if an outfit is good? | |
| ASK_HOW_SCORING (arabizi) | kifech ta3ti note lel lebset? | How do you score outfits? | |
| ASK_HOW_SCORING (arabizi) | kifech el application ta3ref el lebsa behya? | How does the app decide if an outfit is good? | |
| ASK_INSIGHTS | شنوة ناقص في الخزانة متاعي؟ | What's missing in my wardrobe? | |
| ASK_INSIGHTS | شنية الحوايج إلي تنفعني أكثر؟ | Which of my pieces are the most useful? | |
| ASK_INSIGHTS | شنوة لازمني نزيد للخزانة؟ | What should I add to my wardrobe? | |
| ASK_INSIGHTS (arabizi) | chnowa na9es fel khzena mte3i? | What's missing in my wardrobe? | |
| ASK_INSIGHTS (arabizi) | chniya el 7wayej elli tenfa3ni akther? | Which of my pieces are the most useful? | |
| ASK_INSIGHTS (arabizi) | chnowa lazemni nzid lel khzena? | What should I add to my wardrobe? | |
| ASK_LABELS | علاش {a} خذا هالليبال؟ | Why is {a} labelled like that? | |
| ASK_LABELS | قداش التطبيقة متأكدة من {a}؟ | How sure is the app about {a}? | |
| ASK_MY_LISTINGS | وريني الإعلانات متاعي | Show my listings | |
| ASK_MY_LISTINGS | شنية أخبار الإعلانات متاعي؟ | How are my listings doing? | |
| ASK_MY_LISTINGS (arabizi) | warini les annonces mte3i | Show my listings | |
| ASK_MY_LISTINGS (arabizi) | chniya a5bar les annonces mte3i? | How are my listings doing? | |
| ASK_PRICE | بقداش نجم نبيع {a}؟ | How much can I sell {a} for? | |
| ASK_PRICE | قداش نحط سوم {a}؟ | What price for {a}? | |
| ASK_SEARCH | وين نلقى {piece}؟ | Where can I find {piece}? | |
| ASK_SEARCH | نلوج على {piece} | I'm looking for {piece} | |
| ASK_SEARCH | فما {piece} للبيع؟ | Any {piece} for sale? | |
| ASK_SEARCH_PRICE | نحب {piece} بأقل من {price} دينار | I need {piece} under {price} TND | |
| ASK_SEARCH_PRICE | لقالي {piece} بأقل من {price} دينار | Find me {piece} for less than {price} TND | |
| ASK_SELL | عاوني نبيع {a} | Help me sell {a} | |
| ASK_SELL | نحب نبيع {a} | I want to sell {a} | |
| ASK_SIMILAR | لقالي حاجة كيف {a} | Find me something like {a} | |
| ASK_SIMILAR | وين نشري حاجة تشبه ل{a}؟ | Where can I buy something similar to {a}? | |
| ASK_SIMILAR_SCAN | وين نلقى حاجة كيف إلي صورتها؟ | Where can I find something like the piece I scanned? | |
| ASK_SIMILAR_SCAN | لقالي حوايج تشبه للسكان الأخير | Find look-alikes of my last scan | |
| ASK_SIMILAR_SCAN (arabizi) | win nal9a 7aja kif elli sawartha? | Where can I find something like the piece I scanned? | |
| ASK_SIMILAR_SCAN (arabizi) | la9ali 7wayej tchabah lel scan le5er | Find look-alikes of my last scan | |
| ASK_STATS | شنوة فيها الخزانة متاعي؟ | What is my wardrobe made of? | |
| ASK_STATS | قداش عندي من حاجة، وشنية الألوان؟ | How many clothes do I have, and in which colours? | |
| ASK_STATS (arabizi) | chnowa fiha el khzena mte3i? | What is my wardrobe made of? | |
| ASK_STATS (arabizi) | 9addech 3andi men 7aja, w chniya el alwen? | How many clothes do I have, and in which colours? | |
| ASK_TODAY | شنوة نلبس اليوم؟ | What should I wear today? | |
| ASK_TODAY | شنوة نلبس اليوم مع هالطقس؟ | What do I wear today with this weather? | |
| ASK_TODAY | لبسني لليوم | Dress me for today | |
| ASK_TODAY (arabizi) | chnowa nelbes lyoum? | What should I wear today? | |
| ASK_TODAY (arabizi) | chnowa nelbes lyoum m3a hel ta9s? | What do I wear today with this weather? | |
| ASK_TODAY (arabizi) | lebesni lel youm | Dress me for today | |
| ASK_TWINS | عندي حوايج مكررين؟ | Do I own the same thing twice? | |
| ASK_TWINS | فما حوايج يتشابهو برشا عندي؟ | Any duplicates in my wardrobe? | |
| ASK_TWINS (arabizi) | 3andi 7wayej mkarrin? | Do I own the same thing twice? | |
| ASK_TWINS (arabizi) | famma 7wayej yetchabhou barcha 3andi? | Any duplicates in my wardrobe? | |
| ASK_WEATHER | كيفاش الطقس اليوم؟ | What's the weather like today? | |
| ASK_WEATHER | باش تصب اليوم؟ | Is it going to rain today? | |
| ASK_WEATHER (arabizi) | kifech el ta9s lyoum? | What's the weather like today? | |
| ASK_WEATHER (arabizi) | bech tsob lyoum? | Is it going to rain today? | |
| ASK_WHAT_IF | وكان نلبس {c} في بلاصة {b} مع {a}؟ | What if I wear {c} instead of {b} with {a}? | |
| ASK_WHAT_SELL | شنوة لازمني نبيع؟ | What should I sell? | |
| ASK_WHAT_SELL | شنية الحوايج إلي نجم نبيعهم؟ | Which clothes could I sell? | |
| ASK_WHAT_SELL (arabizi) | chnowa lazemni nbi3? | What should I sell? | |
| ASK_WHAT_SELL (arabizi) | chniya el 7wayej elli najem nbi3hom? | Which clothes could I sell? | |
| ASK_WHY_SCORE | علاش {a} مع {b} خذات هالنوطة؟ | Why does {a} with {b} get that score? | |
| ASK_WHY_SCORE | فسرلي النوطة متاع {a} مع {b} | Explain the score of {a} with {b} | |
| ASK_WHY_VERDICT | علاش السكان متاعي خذا هالرأي؟ | Why did my scan get that verdict? | |
| ASK_WHY_VERDICT | علاش التطبيقة قالت هكا على الحاجة إلي صورتها؟ | Why does the app say that about the piece I scanned? | |
| ASK_WHY_VERDICT (arabizi) | 3lech el scan mte3i 5dhe hel ra2y? | Why did my scan get that verdict? | |
| ASK_WHY_VERDICT (arabizi) | 3lech el application 9alet haka 3al 7aja elli sawartha? | Why does the app say that about the piece I scanned? | |
| CONDITION_WORDS.clear | شمس | sunny | |
| CONDITION_WORDS.cloudy | مغيّم | cloudy | |
| CONDITION_WORDS.fog | ضباب | foggy | |
| CONDITION_WORDS.rain | مطر | rainy | |
| CONDITION_WORDS.snow | ثلج | snowy | |
| CONDITION_WORDS.storm | عواصف | stormy | |
| FACTS | الحوايج عندهم نفس الستيل | the pieces share one style | |
| FACTS | الحوايج ستيلهم مختلف برشا | the pieces have quite different styles | |
| FACTS | اللبسة ما تشبهش للستيل متاعك العادي | the outfit is unlike the user's usual style | |
| FACTS | {0} و{1} يمشيو مع بعضهم | (\w+) and (\w+) go together | |
| FACTS | قاعدة هادية من {0} ألوان نوترال | a calm base of (\d+) neutral colours | |
| FACTS | {0} و{1} ما يمشيوش مع بعضهم | (\w+) and (\w+) clash | |
| FACTS | برشا ألوان قوية ({0}) | too many bold colours \((.+)\) | |
| FACTS | موتيف قوي واحد ({0}) | one statement pattern \((\w+)\) | |
| FACTS | حوايج هادية وسادة | calm, plain pieces | |
| FACTS | زوز موتيفات قويين ({0} + {1}) | two bold patterns \((\w+) \+ (\w+)\) | |
| FACTS | لبسة كاملة بالصباط | a complete outfit with shoes | |
| FACTS | ما فماش صباط | no shoes | |
| FACTS | روبة مع سروال | a full piece and a bottom together | |
| FACTS | {0} حوايج من نوع {1} | (\d+) pieces of ([\w-]+) | |
| FACTS | {0} و{1} ما يمشيوش مع بعضهم | ([\w-]+) and ([\w-]+) don't go together | |
| FACTS | ما فماش حاجة أساسية | no main piece | |
| FACTS | ناقص توب ولا سروال | missing a top or a bottom | |
| FIELD_WORDS.category | الصنف | category | |
| FIELD_WORDS.sub_category | النوع | type | |
| FIELD_WORDS.pattern | الموتيف | pattern | |
| FIELD_WORDS.colour | اللون | colour | |
| MISSING_WORDS.shoes | صباط | shoes | |
| MISSING_WORDS.top | توب | a top | |
| MISSING_WORDS.bottom | سروال | a bottom | |
| MISSING_WORDS.main | توب وسروال، ولا روبة | a top and a bottom, or a dress | |
| PART_WORDS.style | الستيل | style | |
| PART_WORDS.colour | الألوان | colours | |
| PART_WORDS.pattern | الموتيفات | patterns | |
| PART_WORDS.structure | التركيبة | structure | |
| SAY_COMPLETE | مع {a}، زيد {added}: اللبسة تاخو {score}/100. | With {a}, add {added}: the outfit scores {score}/100. | |
| SAY_COMPLETE | أحسن حاجة مع {a}: {added} ({score}/100). | Best match for {a}: {added} ({score}/100). | |
| SAY_COMPLETE_NONE | حتى حاجة أخرى في الخزانة متاعك ما تمشي مع {a} توا. حاجة تمشي معاها تعاونك. | Nothing else in your wardrobe goes with {a} yet. A piece that matches it would help. | |
| SAY_COMPLETE_OTHER | زادة تنجم: {others}. | Also good: {others}. | |
| SAY_CORRECTED | إنت صلحت {fields} بروحك. | You corrected the {fields} yourself. | |
| SAY_FRIPERIE_IN | فريب في {city} | friperie seller in {city} | |
| SAY_HANDOFF | هاذا سؤال ل{agent}: اسألو هو ويجاوبك. | That's a question for {agent}: ask it there and it will answer you. | |
| SAY_HANDOFF | {agent} هو إلي يتلهى بهاذا: اسألو ويعاونك. | {Agent} handles that: ask it and it will help you. | |
| SAY_HELLO_AGENT.shopping | عسلامة! نجم نقلك إذا الحاجة إلي صورتها تستاهل تشريها، نلقالك حوايج للبيع في الحوانت والفريب، وحوايج تشبه لحوايجك. شنوة تلوج؟ | Hi! I can tell you if a piece you scanned is worth buying, find clothes for sale in shops and friperie, and find look-alikes of your pieces. What are you looking for? | |
| SAY_HELLO_AGENT.analyst | عسلامة! نجم نقلك شنوة ناقص في الخزانة متاعك، شنية الحوايج إلي تلبسها برشا ولا ما تلبسهاش، شنوة فيها والحوايج إلي عندك منهم زوز. شنوة تحب تعرف؟ | Hi! I can tell you what your wardrobe is missing, which pieces you use most or never, what it is made of and which pieces you own twice. What do you want to know? | |
| SAY_HELLO_AGENT.seller | عسلامة! نجم نلقالك الحوايج إلي تنجم تبيعهم، نقترحلك سوم فريب معقول ونحضرلك الفورمولار متاع البيع. شنية الحاجة إلي تحب تبيعها؟ | Hi! I can find pieces worth selling, suggest a fair friperie price and prepare the Sell form for you. Which piece do you want to sell? | |
| SAY_HELLO_AGENT.explainer | عسلامة! نجم نفسرلك علاش لبسة خذات النوطة متاعها، شنوة يبدلها، علاش حاجة خذات الليبال متاعها وعلاش السكان خذا الرأي متاعو. شنوة نفسرلك؟ | Hi! I can explain why an outfit gets its score, what would change it, why a piece got its labels and why a scan got its verdict. What should I explain? | |
| SAY_HOW_SCORING | كل لبسة تاخو نوطة على 100 من أربعة حاجات: {weights}. اللبسة باهية من {good}/100. الفريق متاع DressMe هو إلي يحط هالأوزان. | Each outfit gets a score out of 100 from four parts: {weights}. An outfit is good from {good}/100. The DressMe team sets these weights. | |
| SAY_INSIGHTS_OUTFITS | الخزانة متاعك تعمل {good} لبسات باهيين. | Your wardrobe makes {good} good outfits. | |
| SAY_LABEL | {field}: {value} (متأكد {conf}%) | {field}: {value} ({conf}% sure) | |
| SAY_LABELS | شنوة خمنت التطبيقة من التصويرة: {labels}. | The app's guesses from the photo: {labels}. | |
| SAY_LISTING | {title} ب{price} دينار ({where}) | {title} at {price} TND ({where}) | |
| SAY_MISSING | باش تعمل لبسات أكثر، زيد {missing}. | To make more outfits, add {missing}. | |
| SAY_MY_LISTING | {title}، {price} دينار: {status} | {title}, {price} TND: {status} | |
| SAY_MY_LISTINGS | الإعلانات متاعك: {list}. | Your listings: {list}. | |
| SAY_NEUTRAL | {n} منهم ألوان نوترال يمشيو مع كل شي تقريبا. | {n} of them are neutral colours that go with almost anything. | |
| SAY_NOTHING_MISSING | ما ناقصك حتى شي أساسي. | Nothing essential is missing. | |
| SAY_NO_LISTINGS | ما عندك حتى إعلان توا. اسألني شنوة تبيع، ولا استعمل الخانة متاع البيع. | You have no listings yet. Ask me what to sell, or use the Sell tab. | |
| SAY_NO_RAIN | ما فماش مطر. | No rain expected. | |
| SAY_NO_SCAN_SIMILAR | ما نشوف حتى حاجة مصورة. صورها في الخانة متاع السكان، ومبعد عاود اسألني. | I don't see a scanned piece. Take a photo in the Scan tab, then ask me again. | |
| SAY_NO_SWAP | حتى حاجة من الخزانة متاعك ما تحسنها بالحق. | No piece of your wardrobe would clearly improve it. | |
| SAY_NO_TWINS | ما فماش حوايج مكررة: الكل مختلفين. | No duplicates: all your pieces look different. | |
| SAY_OPEN_PANEL | حل التفسير باش تشوف وين خزر المودال في التصويرة. | Open the explanation to see where the model looked in the picture. | |
| SAY_PRICE | ل{a}، الحوايج إلي تشبهلها تقول من {low} ل{high} دينار (الوسط {median} دينار، من {count} حوايج). | For {a}, similar listings suggest {low} to {high} TND (middle: {median} TND, from {count} look-alikes). | |
| SAY_PRICE_NONE | ما لقيتش حوايج تشبه ل{a} عندها سوم، ما نجمش نقترح سوم معقول. | I can't find similar listings with a price for {a} yet, so I can't suggest a fair price. | |
| SAY_PROBLEMS | شنوة ينقص النوطة: {facts}. | What lowers it: {facts}. | |
| SAY_RAIN | ممكن تصب، خوذ فيستة معاك. | Rain is likely, take a jacket. | |
| SAY_REJECTED_NOTE | ملاحظة الأدمين: "{note}". | The admin's note: "{note}". | |
| SAY_SEARCH | موجود توا: {list}. | In stock now: {list}. | |
| SAY_SEARCH_NONE | ما لقيت حتى شي موجود يتطابق توا. جرب بلاش حد السوم ولا لون آخر. | I found nothing in stock matching that right now. Try without the price limit or another colour. | |
| SAY_SELL_ASK_PRICE | ما لقيتش حوايج تشبه ل{a} عندها سوم. قلي السوم متاعك ونحضرلك الفورمولار. | I can't find similar listings with a price for {a}. Tell me your price and I'll prepare the Sell form. | |
| SAY_SELL_FORM | حضرتلك الفورمولار متاع البيع: "{title}" ب{price} دينار، الوسط متاع الحوايج إلي تشبهلها. حلّو بالبوطون، زيد المدينة والكونتاكت متاعك وابعثو. أدمين يثبت في كل إعلان قبل ما يشوفوه الناس. | I prepared the Sell form: "{title}" at {price} TND, the middle of similar listings. Open it with the button, add your city and contact and send it. An admin checks each listing before others see it. | |
| SAY_SELL_NEXT | تحب نقلك بقداش تنجم تبيع وحدة منهم؟ | Want a price for one of them? | |
| SAY_SELL_NOTHING | الحوايج متاعك الكل ينفعو في اللبسات: ما نبيع حتى شي توا. | Every piece you own is useful in your outfits: I wouldn't sell any for now. | |
| SAY_SELL_TWINS | عندك زادة حوايج يتشابهو: تنجم تبيع {items}. | You also own near-copies: you could sell {items}. | |
| SAY_SELL_UNMATCHED | {items} ما يمشيو مع حتى شي في الخزانة متاعك. | {items} go with nothing in your wardrobe. | |
| SAY_SIMILAR | حوايج تشبهلها في H&M: {shop}. | Look-alikes at H&M: {shop}. | |
| SAY_SIMILAR_LISTINGS | للبيع توا: {listings}. | For sale now: {listings}. | |
| SAY_SIMILAR_NONE | ما لقيت حتى حاجة تشبهلها توا. | I found no look-alike for it right now. | |
| SAY_SNAPSHOT | شوية أسوام جاية من صورة قديمة، ممكن الستوك تبدل. | Some prices come from an old snapshot, so stock may have changed. | |
| SAY_STATS | عندك {total} حوايج: {categories}. الألوان الأساسية: {colours}. | You have {total} pieces: {categories}. Main colours: {colours}. | |
| SAY_SWAP | أضعف حاجة: {piece}؛ {swap} في بلاصتها تزيد {gain} نقاط. | Weakest piece: {piece}; {swap} instead would add {gain} points. | |
| SAY_TO_CONFIRM | {n} حوايج ما عندهمش لون توا: تنجم تختارو في الخانة متاع الخزانة. | {n} pieces still have no colour: you can set it in the Wardrobe tab. | |
| SAY_TO_NEXT | {n} زايدين يبدلو الرأي. | {n} more would change the verdict. | |
| SAY_TWINS | هاذوما يتشابهو برشا: {pairs}. | These look almost the same: {pairs}. | |
| SAY_UNMATCHED | ما يمشي مع حتى شي توا: {items}. | Goes with nothing yet: {items}. | |
| SAY_UNSURE | موش متأكدة من {fields}: ثبت فيه. | It is not sure about the {fields}: please check it. | |
| SAY_VERDICT | "{verdict}" خاطر تعمل {good} لبسة باهية فيها خير من حوايجك؛ "اشري" يلزمها {buy_min}. | "{verdict}" because it makes {good} good outfit(s) where it beats what you own; "buy" needs {buy_min}. | |
| SAY_VERDICT_TWINS | عندك ديجا حاجة تشبهلها برشا: {items}. | You already own something very similar: {items}. | |
| SAY_VERSATILE | أكثر حوايج تنفع: {items}. | Most useful: {items}. | |
| SAY_WEATHER | اليوم في {place}: {condition}، من {low} ل{high} درجة. | Today in {place}: {condition}, {low} to {high}°C. | |
| SAY_WEATHER_DOWN | ما نجمتش نجيب الطقس متاع اليوم، هاذا اختيار عام. | I can't get today's weather right now, so here is a general pick. | |
| SAY_WHAT_IF | ب{c} في بلاصة {b}: {before} → {after}/100 ({change} نقاط). | With {c} instead of {b}: {before} → {after}/100 ({change} points). | |
| SAY_WHY_SCORE | {score}/100، من {points}. | {score}/100, from {points}. | |
| SAY_WORKS | شنوة يمشي: {facts}. | What works: {facts}. | |
| STATUS_WORDS.pending | تستنى في الأدمين | waiting for an admin | |
| STATUS_WORDS.active | تبان للناس | visible | |
| STATUS_WORDS.rejected | مرفوضة | rejected | |
| STATUS_WORDS.gone | تباعت ولا تنحات | sold or removed | |
| VERDICT_WORDS.buy | اشري | buy | |
| VERDICT_WORDS.think | خمم | think about it | |
| VERDICT_WORDS.skip | خليها | skip | |
| chat.py NO_ANSWER | سامحني، ما كمّلتش الجواب. تنجم تعاود تسأل بكلام آخر؟ | Sorry, I couldn't finish that answer. Could you ask again in other words? | |

## 8. New phrases for model v3 (2026-10-09, NOT reviewed)

Look-alike explanations (`explain_similarity`) in `src/phase4/chat_phrases_agents.py` (end of the file). `dressme-chat-v3` was trained on them as written. **Meaning** is the English version.

| Key | Darija | Meaning | Correction |
|---|---|---|---|
| CONCEPT_WORDS.streetwear | ستريت وير | streetwear | |
| CONCEPT_WORDS.formal | رسمي | formal | |
| CONCEPT_WORDS.sporty | سبور | sporty | |
| CONCEPT_WORDS.casual | كاجوال | casual | |
| CONCEPT_WORDS.classic | كلاسيك | classic | |
| CONCEPT_WORDS.modest | محتشم | modest | |
| CONCEPT_WORDS.trendy | موضة | trendy | |
| CONCEPT_WORDS.party | سهرية | party | |
| CONCEPT_WORDS.denim | دجين | denim | |
| CONCEPT_WORDS.leather | جلد | leather | |
| CONCEPT_WORDS.knit | تريكو | knit | |
| CONCEPT_WORDS.lace | دونتال | lace | |
| CONCEPT_WORDS.satin | ساتان | satin | |
| CONCEPT_WORDS.oversized | واسع | oversized | |
| CONCEPT_WORDS.fitted | لاصق | fitted | |
| CONCEPT_WORDS.floral | ورود | floral | |
| CONCEPT_WORDS.striped | مخطط | striped | |
| CONCEPT_WORDS.checked | كاروه | checked | |
| CONCEPT_WORDS.vintage | فينتاج | vintage | |
| CONCEPT_WORDS.traditional | تقليدي | traditional | |
| ASK_WHY_SIMILAR | علاش {a} و{b} يتشابهو؟ | Why do {a} and {b} look alike? | |
| ASK_WHY_SIMILAR | {a} و{b} يتشابهو؟ | Are {a} and {b} similar? | |
| ASK_WHY_SIMILAR | شنوة يجمع {a} و{b}؟ | What do {a} and {b} have in common? | |
| ASK_WHY_SIMILAR_SCAN | علاش الحاجة إلي صورتها تشبه ل{a}؟ | Why does the piece I scanned look like {a}? | |
| ASK_WHY_SIMILAR_SCAN | الحاجة إلي صورتها تشبه ل{a}؟ | Is what I scanned like {a}? | |
| SAY_SIMILARITY | {a} و{b}: يتشابهو {pct}% في التصاور. | {a} and {b}: {pct}% alike in the pictures. | |
| SAY_NEAR_TWIN | تقريبا كيف كيف. | They are near twins. | |
| SAY_SHARED | يشتركو في: {labels}. | In common: {labels}. | |
| SAY_DIFFERS | يختلفو في: {labels}. | Differences: {labels}. | |
| SAY_BOTH_READ | المودال متاع التصاور يشوف الزوز {concepts}. | The picture model reads both as {concepts}. | |
| SAY_CONTRAST | المودال متاع التصاور يشوف {a} {ca}، أما {b} {cb}. | The picture model reads {a} as {ca}, but {b} as {cb}. | |
| SAY_SCAN_PIECE | الحاجة إلي صورتها | the piece you scanned | |
