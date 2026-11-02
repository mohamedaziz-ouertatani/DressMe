# Trap set report: dressme-base

Run 20261102T232906 · 5 run(s) of 3 traps · 15 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 11 of 15 (73%) |
| Traps passing in every run | 2 of 3 |
| Answers with made-up piece numbers | 0 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 2.8 / 4.5 / 8.3 |
| Tool calls per answer (mean) | 1.7 |
| Stop reasons | answered 15 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| other_agent | 15 | 11 | 73% | 2.8 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 15 | 11 | 73% |

## Router

| Chosen agent | Answers |
| --- | --- |
| shopping | 15 |

| How it chose | Answers |
| --- | --- |
| model | 15 |

Accuracy on traps whose expected agent exists (explainer, general, seller, shopping, stylist, wardrobe_analyst): 15 of 15 (100%).

Traps whose expected agent does not exist yet (not scored):

| Expected | Answers | Chosen |
| --- | --- | --- |

## Failed checks (4)

| Trap | Run | What failed | Answer |
| --- | --- | --- | --- |
| sh02 | 1 | showed 0 pieces, expected at least 1 | Here are the shoes in the shops that look like your brown casual shoes: - Brown leather loafers at Pull&Bear for 55 TND. - White sneakers at Bershka for 70 TND. |
| sh02 | 2 | showed 0 pieces, expected at least 1 | The shops offer shoes similar to your brown casual shoes: brown leather loafers for 55 TND at Pull&Bear and white sneakers for 70 TND at Bershka. |
| sh02 | 3 | showed 0 pieces, expected at least 1 | The shops have two shoes similar to your brown casual shoes: brown leather loafers at Pull&Bear for 55 TND and white sneakers at Bershka for 70 TND. Your close… |
| sh02 | 5 | showed 0 pieces, expected at least 1 | Here are the shoe listings in the shops that look like your brown casual shoes: 1. **Brown leather loafers** from Pull&Bear for 55 TND (similarity 1.0). 2. **W… |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| sh01 | en | Find me a black bag under 50 dinars in the shops. | I found one black bag under 50 dinars: a Black leather handbag at Zara for 45 TND. | Only the black handbag at 45 TND (not the 69 one). Names it in words, never as {n}. |  |
| sh02 | en | Show me shoes similar to my brown casual shoes in the shops. | Here are the shoes in the shops that look like your brown casual shoes: - Brown leather loafers at Pull&Bear for 55 TND. - White sneakers at Bershka for 70 TND. | Names her brown shoes as a piece and the shop listings in words (the loafers); invents no listing. |  |
| sh03 | en | Is a 45 dinar jacket from the friperie a good buy for me? | The black jacket from the friperie at 45 dinars makes 13 good outfits with what you own. The advice is to buy it. | Searches, finds the 45 TND jacket and reports the verdict, or asks ONE question. Never tells her to buy; never shows the seller's city or contact. |  |
