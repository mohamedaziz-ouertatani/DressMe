DRESSME ENCODER VALIDATION LAB - DECISION RULE
Written and committed BEFORE any accuracy score is computed. Date: 2026-11-01

1. Requirements (a model must pass all):
   - open weights, downloadable directly (no form, no login);
   - licence allows academic use;
   - at most 500M parameters;
   - the sanity grid passes.
   CPU speed is reported, not a requirement (decision of 2026-11-01).
2. Main score: MRR on the TEST split, English-words questions that have an
   answer, of the frozen exam (questions-only fingerprint
   08e61000fd67fbcecb6b2548122633b16eb99391ab444e95fdf1df18e7377867).
3. Settings are chosen on VALIDATION only, then applied unchanged to TEST:
   - prefix for word questions: raw or "a photo of", whichever gives the
     higher validation words-MRR (tie: raw);
   - cut, per model and per track: the lowest threshold on a 0.001 grid
     giving precision >= 0.90 on validation, answering at least
     max(20, n/10) questions.
4. Paired bootstrap: 1,000 resamples of the test questions, the same
   resamples for all models, 95% percentile interval (2.5% to 97.5%).
5. Disqualified on photos: the paired interval of (photo MRR minus the best
   photo MRR) is entirely below -0.03. A disqualified model cannot win.
6. Winner = highest main score among models not disqualified.
7. Tie: every model whose paired interval of the gap to the winner includes
   0 is tied with it. Break the tie by (a) photo MRR, then (b) smaller
   parameter count.
8. Reported but not deciding: precision and coverage at the cut, the
   no-answer rate, French and Arabic, CPU speed, GPU time.
9. The model names are revealed only after the winner is computed.
