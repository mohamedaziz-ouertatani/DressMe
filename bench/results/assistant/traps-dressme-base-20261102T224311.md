# Trap set report: dressme-base

Run 20261102T224311 · 30 run(s) of 1 traps · 30 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 23 of 30 (77%) |
| Traps passing in every run | 0 of 1 |
| Answers with made-up piece numbers | 2 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 2.0 / 2.2 / 3.0 |
| Tool calls per answer (mean) | 1.7 |
| Stop reasons | answered 30 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| grounded | 30 | 23 | 77% | 2.0 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 30 | 23 | 77% |

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

## Failed checks (7)

| Trap | Run | What failed | Answer |
| --- | --- | --- | --- |
| g01 | 3 | expected one of ['suggest_outfits'], called no tool; showed 0 pieces, expected at least 2 | To give you the best outfit suggestions for today, could you tell me what occasion you're planning for? For example: work, university, an outing, or just every… |
| g01 | 4 | expected one of ['suggest_outfits'], called no tool; showed 0 pieces, expected at least 2 | To give you the best suggestions for today, could you tell me what occasion you have in mind (e.g., everyday, work, outing)? |
| g01 | 5 | invented piece numbers [7, 8] | Wear {2} with {5} and: the white top makes the black skirt look fresh, and the sandals suit today's 15 degrees. Or wear {6} with {3} and: the blue shirt pairs … |
| g01 | 7 | expected one of ['suggest_outfits'], called no tool; showed 0 pieces, expected at least 2 | To give you the best outfit suggestions for today, could you tell me what occasion you're planning for? For example, work, a casual day out, or something speci… |
| g01 | 14 | expected one of ['suggest_outfits'], called no tool; showed 0 pieces, expected at least 2 | To give you the best outfit suggestions for today, could you tell me what occasion you're planning for? For example, work, university, an outing, or something … |
| g01 | 22 | invented piece numbers [2, 5, 4, 7]; expected one of ['suggest_outfits'], called ['get_weather']; showed 0 pieces, expected at least 2 | It's clear and slightly rainy today, with a temperature of 15 degrees in mid-season. Here are two outfit suggestions: - Wear with: The white top brings freshne… |
| g01 | 25 | expected one of ['suggest_outfits'], called ['get_weather']; showed 0 pieces, expected at least 2 | I don't know what occasion you have today. Would you like suggestions for everyday wear, work, or maybe an outing? |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| g01 | en | What should I wear today? | Wear {6} with {2}, {3}, {4} and {5}: the colours match well and this outfit fits today's clear but rainy weather. Alternatively, try {1} with {2}, {3}, {4} and {5}: the bold pattern adds interest while keeping it suitable for mid-season conditions. | One or two outfits from her pieces, short reasons. |  |
