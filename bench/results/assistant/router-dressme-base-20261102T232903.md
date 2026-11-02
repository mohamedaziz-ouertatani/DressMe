# Router test: dressme-base

Run 20261102T232903 · split: dev · 5 run(s) of 32 cases · 160 answers · agents in the file: stylist, general, wardrobe_analyst, explainer, seller, shopping

## Totals

| Measure | Value |
| --- | --- |
| Router accuracy (cases whose expected agent exists) | 160 of 160 (100%) |
| Chosen by the model | 160 of 160 |
| Fell back to the keywords | 0 |
| Fell back to the default agent | 0 |
| Seconds per router call: median / max | 0.18 / 0.28 |

If the model was not chosen for most answers, the router did not really run: check Ollama.

## By expected agent

| Expected | Cases | Answers | Right | Rate |
| --- | --- | --- | --- | --- |
| stylist | 7 | 35 | 35 | 100% |
| wardrobe_analyst | 5 | 25 | 25 | 100% |
| explainer | 5 | 25 | 25 | 100% |
| seller | 5 | 25 | 25 | 100% |
| shopping | 5 | 25 | 25 | 100% |
| general | 5 | 25 | 25 | 100% |

## Mix-ups (expected to chosen)

None.

## Cases that were not always right (0)

None.

## Not scored yet (the expected agent is not built)

None: every expected agent exists.

Tune the descriptions and examples on the dev split only. Run the test split once per decision.
