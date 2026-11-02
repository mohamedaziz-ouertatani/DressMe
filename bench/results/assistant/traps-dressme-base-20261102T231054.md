# Trap set report: dressme-base

Run 20261102T231054 · 5 run(s) of 3 traps · 15 answers · languages: en · API http://localhost:8000

## Totals

| Measure | Value |
| --- | --- |
| Answers passing every automatic check | 13 of 15 (87%) |
| Traps passing in every run | 2 of 3 |
| Answers with made-up piece numbers | 0 |
| Answers writing the user's own numbers as pieces | 0 |
| Answers where code repaired the user's number (shown as plain text) | 0 |
| Answers showing a piece the trap forbids (wrong or not owned) | 0 |
| Errors (not HTTP 200) | 0 |
| Seconds per answer: median / 90th percentile / max | 2.8 / 3.1 / 3.7 |
| Tool calls per answer (mean) | 2.3 |
| Stop reasons | answered 15 |
| `<think>` blocks stripped | 0 |

Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.

## By category

| Category | Answers | Passed | Rate | Median seconds |
| --- | --- | --- | --- | --- |
| other_agent | 15 | 13 | 87% | 2.8 |

## By language

| Language | Answers | Passed | Rate |
| --- | --- | --- | --- |
| en | 15 | 13 | 87% |

## Router

| Chosen agent | Answers |
| --- | --- |
| explainer | 15 |

| How it chose | Answers |
| --- | --- |
| model | 15 |

Accuracy on traps whose expected agent exists (explainer, general, stylist, wardrobe_analyst): 15 of 15 (100%).

Traps whose expected agent does not exist yet (not scored):

| Expected | Answers | Chosen |
| --- | --- | --- |

## Failed checks (2)

| Trap | Run | What failed | Answer |
| --- | --- | --- | --- |
| e03 | 1 | answered in fr, expected en | L'évaluation d'une tenue est basée sur quatre éléments : le style (35 %), la couleur (30 %), le motif (15 %) et la structure (20 %). Une tenue est considérée c… |
| e03 | 2 | answered in fr, expected en | L'évaluation d'un look se divise en quatre parties : le style (35 %), la couleur (30 %), le motif (15 %) et la structure (20 %). Un look est considéré comme bo… |

## Review sheet (read each answer, mark OK or not)

| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |
| --- | --- | --- | --- | --- | --- |
| e01 | en | Why did my pink jacket and black skirt get that score? | {1} with {9} scores 71: the colours match perfectly, but the outfit lacks a top, which lowers its structure score. | Finds both pieces, gives the score the tool gave and the reasons in plain words; invents no number. |  |
| e02 | en | Which piece weakens my pink jacket and black skirt outfit the most? | Your pink jacket {1} and black skirt {9} outfit has no weak piece to swap. | Names the weakest piece and the swap explain_outfit gave, or says neither piece is clearly weak. |  |
| e03 | en | How does the outfit scoring work? | L'évaluation d'une tenue est basée sur quatre éléments : le style (35 %), la couleur (30 %), le motif (15 %) et la structure (20 %). Une tenue est considérée comme bonne à partir de 60 points. Chaque élément peut ne pas être calculé s'il n'existe pas, ce qui fait augmenter la part des autres élémen… | Four parts with the shares the tool gave (style 35, colour 30, structure 20, pattern 15); invents none. |  |
