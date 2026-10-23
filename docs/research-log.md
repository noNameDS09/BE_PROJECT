# Research log

Every experiment run, newest first. One entry per run:
date · who · command · config hash(es) · dataset/split · result summary · link to results.

Runs on test companies are marked **FINAL**.

---

## 2026-10-20 · Ayush (with Claude) · dev tuning round 1 + pilot 3 (dev)

**Why:** in pilot 2 (gold_num dev, 24 items, nim-nemotron-super) Loupe scored 0.88 against ReAct's 1.00.
All 3 Loupe misses were false refusals: the first answer was right, but the code verifier rejected it,
and after one revision nothing verified, so Loupe abstained.

| Item | First answer | Why it was rejected | Fix |
|---|---|---|---|
| MMM equity Q2 FY2023 | $7,798 million [E1] ✓ | "3M" parsed as 3 million | numbers glued to m/k/bn without `$` are names |
| MMM operating income FY2023 | -10,689 million USD [E1] ✓ | leading `-` stripped as a bullet | only `- ` followed by a space is a bullet |
| VZ long-term debt Q2 FY2025 | $123.9 billion [E2] (value is in E4) | "30" in "June 30" checked as a value; wrong citation | skip day numbers after a month; revision feedback names the evidence that holds the number |

- **Measurement fixes** (verifier: names, signs, dates, loss wording) apply to every arm. Pilot 2 rows were
  deleted and all arms re-run, with a backup in `data/processed/results.pilot2-backup.duckdb`.
- **Loupe-specific change:** citation-repair hint in the revision step. This counts as one dev tuning round
  for Loupe. To keep the comparison fair (hypotheses.md §6), every other arm also gets one dev tuning
  round before the test split.

**Pilot 3 command** (dev only, seeded):
`loupe eval run {gold_num,gold_calc,gold_trick} --split dev --limit 24 --arm b0 --arm rag --arm react --arm loupe --model nim-nemotron-super --judge ministral-14b`

Results: see `docs/pilot-notes.md`.

## 2026-10-23 · Ayush (with Claude) · dev tuning round 2 (Loupe) + gateway fix

- **Loupe routing:** the distress-score tool was only offered for `open_analysis` questions. On the
  demo "How did Diebold Nixdorf's Altman Z'' distress score change from fiscal 2022 to 2024, and
  which 8-K events explain it?" Loupe routed to trend + event, never got the tool, and abstained.
  `distress_score` is now also offered for `calc` and `trend` intents. Baselines are unaffected
  (they only get generic tools, D21). This is Loupe's second dev tuning round. Every other method
  gets the same number of rounds before the test split.
- **Gateway:** OpenRouter free providers sometimes answer HTTP 200 with no choices; this crashed
  ReAct with `IndexError`. It is now treated as a provider outage and retried.
