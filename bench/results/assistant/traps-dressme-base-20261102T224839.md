# Trap set report: dressme-base

Run 20261102T224839 · 30 run(s) of 1 traps · 30 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 28 of 30 (93%) |
| Traps passing in every run | 0 of 1 |
| Answers with made-up piece numbers | 2 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 1.8 / 1.9 / 2.1 |
| Tool calls per answer (mean) | 2.0 |
| Stop reasons | answered 30 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| grounded | 30 | 28 | 93% | 1.8 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 30 | 28 | 93% |

## Router

| Chosen agent | Answers |
| --- | --- |
| stylist | 30 |

| How it chose | Answers |
| --- | --- |
| button | 30 |

Accuracy on traps whose expected agent exists (general, stylist, wardrobe_analyst): 30 of 30 (100%).

Traps whose expected agent does not exist yet (not scored):

| Expected | Answers | Chosen |
| --- | --- | --- |

## Failed checks (2)

| Trap | Run | What failed | Answer |
| --- | --- | --- | --- |
| g01 | 16 | invented piece numbers [7] | Wear {2} with {5} and: the white top makes the black skirt look fresh, and the sandals suit today's 15 degrees. Or try {6} with {2} and {3}: this combination o… |
| g01 | 19 | invented piece numbers [7] | Wear {2} with {5} and: the white top makes the black skirt look fresh, and the sandals suit today's 15 degrees. Alternatively, try {6} with {2} and {3}: this c… |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| g01 | en | What should I wear today? | Wear {6} with {2}, {3}, {4} and {5}: the calm pattern suits today's clear but rainy weather, and the complete structure fits a mid-season everyday look. | One or two outfits from her pieces, short reasons. |  |
