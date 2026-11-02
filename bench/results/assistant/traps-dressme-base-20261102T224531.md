# Trap set report: dressme-base

Run 20261102T224531 · 30 run(s) of 1 traps · 30 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 27 of 30 (90%) |
| Traps passing in every run | 0 of 1 |
| Answers with made-up piece numbers | 2 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 2.0 / 2.3 / 2.6 |
| Tool calls per answer (mean) | 1.9 |
| Stop reasons | answered 30 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| grounded | 30 | 27 | 90% | 2.0 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 30 | 27 | 90% |

## Failed checks (3)

| Trap | Run | What failed | Answer |
| --- | --- | --- | --- |
| g01 | 9 | invented piece numbers [7] | Wear {2} with {5} and: the white top makes the black skirt look fresh, and the sandals suit today's 15 degrees. Alternatively, try {6} with {2} and {3}, which … |
| g01 | 15 | invented piece numbers [2, 5, 3, 7]; expected one of ['suggest_outfits'], called ['get_weather']; showed 0 pieces, expected at least 2 | It's clear with some rain and the temperature is 15 degrees. Here are two outfit suggestions for today: Wear with: The white top will look fresh against the bl… |
| g01 | 23 | expected one of ['suggest_outfits'], called no tool; showed 0 pieces, expected at least 2 | To give you the best suggestions for today, could you tell me what occasion you're planning for? For example, are you going to work, university, or just runnin… |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| g01 | en | What should I wear today? | Wear {2} with {3}, {4}, and {5}: the outfit has a complete structure and fits today's clear weather, which is 15 degrees. Or try {6} with {2}, {3}, {4}, and {5}: this option offers a calmer pattern while still being suitable for the mid-season conditions. | One or two outfits from her pieces, short reasons. |  |
