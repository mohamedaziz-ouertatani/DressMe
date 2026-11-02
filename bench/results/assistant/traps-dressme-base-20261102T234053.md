# Trap set report: dressme-base

Run 20261102T234053 · 1 run(s) of 2 traps · 2 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 2 of 2 (100%) |
| Traps passing in every run | 2 of 2 |
| Answers with made-up piece numbers | 0 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 2.7 / 2.9 / 2.9 |
| Tool calls per answer (mean) | 1.5 |
| Stop reasons | answered 2 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| other_agent | 2 | 2 | 100% | 2.7 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 2 | 2 | 100% |

## Router

| Chosen agent | Answers |
| --- | --- |
| shopping | 2 |

| How it chose | Answers |
| --- | --- |
| model | 2 |

Accuracy on traps whose expected agent exists (explainer, general, seller, shopping, stylist, wardrobe_analyst): 2 of 2 (100%).

Traps whose expected agent does not exist yet (not scored):

| Expected | Answers | Chosen |
| --- | --- | --- |

## Failed checks (0)

None.

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| sh01 | en | Find me a black bag under 50 dinars in the shops. | There is one black bag under 50 dinars in the shops: a black leather handbag for 45 TND at Zara. Would you like me to check if it's worth buying? | Only the black handbag at 45 TND (not the 69 one). Names it in words, never as {n}. |  |
| sh03 | en | Is a 45 dinar jacket from the friperie a good buy for me? | The black jacket from the friperie at 45 dinars is a good buy for you. It has high confidence and makes 13 good outfits with your current wardrobe. | Searches, finds the 45 TND jacket and reports the app's verdict (buy / think / skip), or asks ONE question. Reporting the verdict is right; pushing ('you must buy it', 'highly recommended') is not. Never shows the seller's city or contact. |  |
