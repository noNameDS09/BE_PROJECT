# Research log

Every experiment run, newest first. One entry per run:
date · who · command · config hash(es) · dataset/split · result summary · link to results.

Runs on test companies are marked **FINAL**.

---

## 2026-10-14 · team · P1 data layer build

**Not an experiment.** No LLM was called and no metric computed; this entry
exists because the corpus the later experiments will use was built here, and a
result is only reproducible if the data underneath it is recorded.

- **Command:** `loupe ingest` (19 FinanceBench candidates, FY2023–25, 10-K/10-Q/8-K)
- **Corpus:** 19 companies, CIKs resolved live against SEC `company_tickers.json`
- **Stack:** edgartools 5.62, DuckDB, BM25 hybrid index
- **Result at this date: 6 of 19 companies ingested** — 350 filings, 1,905 sections,
  **26,117 chunks**, 843 XBRL facts. The run was interrupted (server restart) after
  BBY; BA had begun but was not finished, so it reports 0. Ingest is resumable:
  re-running `loupe ingest` skips filings already stored and continues from there.
  **Coverage therefore does not yet meet P1's 95% target** — re-run to completion
  before quoting any coverage figure.
- **Known gaps at this date:**
  - Prices absent (D14): both free providers blocked from the dev network. Blocks
    P5 forecast backtests until a provider is chosen.
  - `event_candidates` still empty: the second half of the 25-company universe
    is not selected. `loupe scan-risk` produces the ranking; the choice is the team's.
  - Universe not frozen: no dev/test split assigned (P0 exit still open).

**Ablation relevance:** retrieval is BM25-only (D15). Any RQ4 claim about
embeddings must re-run with `dense_model` set, on the same corpus.
