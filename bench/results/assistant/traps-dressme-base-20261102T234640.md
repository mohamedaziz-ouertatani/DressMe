# Trap set report: dressme-base

Run 20261102T234640 · 10 run(s) of 2 traps · 20 answers · languages: en · API http://localhost:8000

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
| Seconds per answer: median / 90th percentile / max | 3.7 / 4.8 / 7.1 |
| Tool calls per answer (mean) | 2.0 |
| Answers that used handoff | 0 |
| Stop reasons | answered 20 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| other_agent | 20 | 0 | 0% | 3.7 |

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
| h01 | 1 | expected a handoff | Your pink jacket {1} and black skirt {9} actually score a decent 71 out of 100: the colours work well (+colour_pair) and the pattern is calm (+pattern_calm), b… |
| h02 | 1 | expected a handoff | To find out if a black bag is worth buying and what it might match with your wardrobe, I need to see specific listings first. Could you point me to one or tell… |
| h01 | 2 | expected a handoff | Your pink jacket and black skirt outfit scores 71: the colours work well together, but the outfit is incomplete because it lacks a top. The scoring tool indica… |
| h02 | 2 | expected a handoff | The black leather handbag at Zara (45 TND) is not recommended for purchase as it does not create any good outfits with your current wardrobe. However, there ar… |
| h01 | 3 | expected a handoff | Your pink jacket ({1}) and black skirt ({9}) outfit scores 71: the colours work well, but the outfit is incomplete because it lacks a top (-structure_incomplet… |
| h02 | 3 | expected a handoff | The black leather handbag at Zara (45 TND) is not worth buying as it doesn't make any good outfits with what you own. You do have a black laptop bag and a pink… |
| h01 | 4 | expected a handoff | To explain your outfit's score and suggest improvements, I need to identify the specific pieces you're referring to. Could you tell me more about your pink jac… |
| h02 | 4 | expected a handoff | A black bag from the shops might be worth considering. The black mini backpack at Bershka costs 69 TND, while the black leather handbag at Zara is 45 TND. Woul… |
| h01 | 5 | expected a handoff | To explain your outfit's score and suggest a better combination, I need to know which specific pieces you are referring to. Could you please provide the number… |
| h02 | 5 | expected a handoff | To give you a specific verdict on whether a black bag is worth buying and which items in your wardrobe it might match, I need to see the actual listings availa… |
| h01 | 6 | expected a handoff | Your pink jacket {1} and black skirt {9} outfit scores 71: the colours work perfectly, but the structure is incomplete because it lacks a top. The scoring syst… |
| h02 | 6 | expected a handoff | The black leather handbag from Zara (45 TND) is not recommended to buy as it doesn't make any good outfits with what you own. However, the tool does note that … |
| h01 | 7 | expected a handoff | To answer your question, I need to know which specific pieces are considered part of that outfit to calculate its score and identify the weakest link. Could yo… |
| h02 | 7 | expected a handoff | The black leather handbag from Zara (45 TND) is recommended to be skipped as it doesn't create any good outfits with your current wardrobe. However, it could s… |
| h01 | 8 | expected a handoff | To explain your outfit score and suggest a better combination, could you tell me the specific numbers (piece IDs) of your pink jacket and black skirt from this… |
| h02 | 8 | expected a handoff | The black mini backpack (listing 2) at Bershka is priced at 69 dinars. It would make 0 good outfits with your current wardrobe. The black leather handbag (list… |
| h01 | 9 | expected a handoff | Your pink jacket and black skirt outfit scores 71: the colours match perfectly but the structure is incomplete because it lacks a top. There's no better swap f… |
| h02 | 9 | expected a handoff | The black leather handbag at Zara (45 TND) isn't recommended to buy as it doesn't create any good outfits with your current wardrobe. The system found no stron… |
| h01 | 10 | expected a handoff | Your pink jacket {1} and black skirt {9} outfit actually scores 71: the colours match well, but the structure is incomplete because it lacks a top. Since neith… |
| h02 | 10 | expected a handoff | To find out if a black bag from the shops is worth buying, I'll need to see some listings first. Could you specify a maximum price for the bag? This will help … |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| h01 | en | Why is my pink jacket and black skirt outfit scored low, and what should I wear instead? | Your pink jacket {1} and black skirt {9} actually score a decent 71 out of 100: the colours work well (+colour_pair) and the pattern is calm (+pattern_calm), but the outfit is incomplete because it lacks a top (-structure_incomplete). Since there's no single weak piece to swap for, adding a top wou… | The first part (why it scores what it does) comes from score_outfit / explain_outfit, the second (what to wear) from suggest_outfits. Neither part invented. |  |
| h02 | en | Would a black bag from the shops be worth buying, and what would it go with in my wardrobe? | To find out if a black bag is worth buying and what it might match with your wardrobe, I need to see specific listings first. Could you point me to one or tell me more details about the bag you're interested in, such as its price or where it's listed? This will help me give you a more precise recom… | The verdict comes from buy_advice; what it goes with from the wardrobe tools. Never tells her to buy; listings named in words. |  |
