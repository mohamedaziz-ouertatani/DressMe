# Trap set report: dressme-base

Run 20261102T234959 · 10 run(s) of 2 traps · 20 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 0 of 20 (0%) |
| Traps passing in every run | 0 of 2 |
| Answers with made-up piece numbers | 0 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 4.1 / 6.3 / 7.5 |
| Tool calls per answer (mean) | 2.2 |
| Answers that used handoff | 0 |
| Stop reasons | answered 20 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| other_agent | 20 | 0 | 0% | 4.1 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 20 | 0 | 0% |

## Router

| Chosen agent | Answers |
| --- | --- |
| explainer | 10 |
| shopping | 10 |

| How it chose | Answers |
| --- | --- |
| model | 20 |

Accuracy on traps whose expected agent exists (explainer, general, seller, shopping, stylist, wardrobe_analyst): 20 of 20 (100%).

Traps whose expected agent does not exist yet (not scored):

| Expected | Answers | Chosen |
| --- | --- | --- |

## Handoff (answers that used it, per trap)

None.

## Failed checks (20)

| Trap | Run | What failed | Answer |
| --- | --- | --- | --- |
| h01 | 1 | expected a handoff | Your pink jacket ({1}) and black skirt ({9}) outfit scores 71: the colours are a plus, but the structure is incomplete because there's no top. The score doesn'… |
| h02 | 1 | expected a handoff | The black leather handbag from Zara (listing 1) at 45 TND is not recommended to buy, as it doesn't make any new good outfits with your current wardrobe. Howeve… |
| h01 | 2 | expected a handoff | To understand why your outfit scores low and suggest better alternatives, I'll first need to identify the specific pieces in your wardrobe that match your desc… |
| h02 | 2 | expected a handoff | Based on the listings I found: - The black mini backpack from Bershka (listing 1) at 69 TND is a skip with high confidence. It makes no good outfits with what … |
| h01 | 3 | expected a handoff | Your pink jacket ({1}) and black skirt ({9}) outfit actually scores 71, not low: the colours work well (+colour_pair), but the outfit lacks a top (-structure_i… |
| h02 | 3 | expected a handoff | The verdict for both black bags is "skip" with high confidence. Neither makes good outfits based on the analysis provided, and the specific outfit combinations… |
| h01 | 4 | expected a handoff | Your pink jacket and black skirt outfit scores 71: the colours match well, but the structure is incomplete because it lacks a top. The explain_outfit tool did … |
| h02 | 4 | expected a handoff | To determine if a black bag is worth buying and how it might fit your wardrobe, I need to see some specific listings. Could you provide me with the listing num… |
| h01 | 5 | expected a handoff | To find out why your outfit scores low and suggest a better alternative, I need to identify the specific pieces in your wardrobe first. Could you confirm if yo… |
| h02 | 5 | expected a handoff | Both black bags from the shops are not recommended for purchase. The Bershka bag (listing 1) and the Zara bag (listing 2) both have a high confidence skip verd… |
| h01 | 6 | expected a handoff | Your pink jacket ({1}) and black skirt ({9}) outfit actually scores 71/100: the colours are good (+colour_pair) and the patterns don't compete (+pattern_calm),… |
| h02 | 6 | expected a handoff | The black mini backpack from Bershka (69 TND) and the black leather handbag from Zara (45 TND) both result in a "skip" verdict, meaning they are not recommende… |
| h01 | 7 | expected a handoff | To explain why your outfit scores low and suggest improvements, I need to see the specific pieces you are wearing together. Could you tell me the names of your… |
| h02 | 7 | expected a handoff | The black leather handbag from Zara (listing 2) is priced at 45 dinars but is not recommended for purchase, as it does not create any new good outfits with you… |
| h01 | 8 | expected a handoff | To understand why your outfit scores low and to suggest better alternatives, let’s first look at how the scoring works for outfits like yours. Could you tell m… |
| h02 | 8 | expected a handoff | To determine if a black bag is worth buying and what it might match with your wardrobe, I need to see specific listings or find out which pieces you already ow… |
| h01 | 9 | expected a handoff | Actually, the outfit of your pink jacket ({1}) and black skirt ({9}) scores 71, not low: the colours work perfectly (+colour_pair), the patterns are calm toget… |
| h02 | 9 | expected a handoff | To determine if a black bag from the shops is worth buying, I need to find specific listings that match your description. Additionally, to know what it would g… |
| h01 | 10 | expected a handoff | Your pink jacket ({1}) and black skirt ({9}) actually score a 71: the colours work perfectly (+colour_pair) and the patterns are calm (+pattern_calm), but the … |
| h02 | 10 | expected a handoff | To determine if a black bag is worth buying, I need to see specific listings. Could you tell me which black bags you are interested in, or should I search for … |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| h01 | en | Why is my pink jacket and black skirt outfit scored low, and what should I wear instead? | Your pink jacket ({1}) and black skirt ({9}) outfit scores 71: the colours are a plus, but the structure is incomplete because there's no top. The score doesn't go up by swapping either piece since both already fit together well. If you want a complete look, adding a top would help. | The first part (why it scores what it does) comes from score_outfit / explain_outfit, the second (what to wear) from suggest_outfits. Neither part invented. |  |
| h02 | en | Would a black bag from the shops be worth buying, and what would it go with in my wardrobe? | The black leather handbag from Zara (listing 1) at 45 TND is not recommended to buy, as it doesn't make any new good outfits with your current wardrobe. However, you already own a black laptop-bag and a pink handbag. Generally, a black bag would be versatile and could complement many items in your … | The verdict comes from buy_advice; what it goes with from the wardrobe tools. Never tells her to buy; listings named in words. |  |
