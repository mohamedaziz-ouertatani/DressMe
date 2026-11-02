# Router test: dressme-base

Run 20261102T223940 · split: test · 5 run(s) of 19 cases · 95 answers · agents in the file: stylist, general, wardrobe_analyst

## Totals

| Measure | Value |
| --- | --- |
| Router accuracy (cases whose expected agent exists) | 50 of 50 (100%) |
| Chosen by the model | 95 of 95 |
| Fell back to the keywords | 0 |
| Fell back to the default agent | 0 |
| Seconds per router call: median / max | 0.14 / 0.20 |

If the model was not chosen for most answers, the router did not really run: check Ollama.

## By expected agent

| Expected | Cases | Answers | Right | Rate |
| --- | --- | --- | --- | --- |
| stylist | 3 | 15 | 15 | 100% |
| wardrobe_analyst | 4 | 20 | 20 | 100% |
| general | 3 | 15 | 15 | 100% |

## Mix-ups (expected to chosen)

None.

## Cases that were not always right (0)

None.

## Not scored yet (the expected agent is not built)

| Expected | Answers | Chosen |
| --- | --- | --- |
| explainer | 15 | stylist 10, general 5 |
| seller | 15 | wardrobe_analyst 10, general 5 |
| shopping | 15 | stylist 15 |

Tune the descriptions and examples on the dev split only. Run the test split once per decision.
