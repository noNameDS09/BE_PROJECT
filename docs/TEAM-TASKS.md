# Parallel work guide (second machine)

**Who this is for:** a teammate running Loupe on their own machine, with their own free API keys and an NVIDIA GPU.

**Why it helps:** free-tier limits are **per account**, so two people running different models get twice the experiment throughput. The GPU makes the embedding jobs take minutes instead of hours.

## 0. One-time setup (≈15 min)

1. **Get the code.** Pull the latest `main`, then install:
   ```bash
   git pull origin main
   uv sync --extra gpu
   uv pip install --reinstall torch --index-url https://download.pytorch.org/whl/cu124
   ```
   Then always run commands as `uv run --no-sync loupe …` (see `docs/GPU-INDEX-BUILD.md`).
2. **Unzip `loupe-data-bundle.zip`** (from Ayush) **in the repo root.** It creates:
   - `data/processed/sec/`: parsed filings
   - `data/processed/loupe.duckdb`: XBRL facts and 8-K events
   - `data/processed/eval/`: converted benchmark questions
   - `data/raw/sec/manifest.jsonl`
   - `data/processed/index/DEFAULT`
3. **Check the search index.** It's the one you built, at `data/processed/index/c1200o150-bge-small/`.
4. **Create your `.env`.** Copy `.env.example` to `.env` and add **your own** keys. Free keys:
   - **NVIDIA:** build.nvidia.com
   - **Ollama Cloud:** ollama.com
   - **Mistral:** console.mistral.ai, Experiment plan
   - **Google:** aistudio.google.com, for Gemini
   - **Groq:** console.groq.com
   - **OpenRouter:** openrouter.ai
   - Set `SEC_USER_AGENT` to `"Loupe research <your email>"`.
5. **Verify.** All four should succeed:
   ```bash
   uv run --no-sync loupe models check --only oc-gemma4-31b --only nim-gpt-oss-20b
   uv run --no-sync loupe index check
   uv run --no-sync loupe search "cybersecurity incident" --company UNH --form 8-K
   uv run --no-sync pytest -q
   ```

## Tasks

### T1 · GPU: benchmark document indexes (≈30 min)
Unzip `loupe-gpu-chunks.zip` (from Ayush) in the repo root. It creates `data/processed/index/docs-financebench/chunks.jsonl` and `docs-finder/chunks.jsonl`. Then:
```bash
uv run --no-sync loupe index build --device cuda --from-chunks data/processed/index/docs-financebench/chunks.jsonl --out data/processed/index/docs-financebench
uv run --no-sync loupe index build --device cuda --from-chunks data/processed/index/docs-finder/chunks.jsonl --out data/processed/index/docs-finder
```
**Send back:** both folders zipped (`docs-financebench/`, `docs-finder/`), plus the build times.

### T2 · Retrieval study, no LLM calls (≈1–2 h, mostly waiting)
This tests how well search finds the gold evidence (research question 4). Run every line and keep the output:
```bash
for ds in financebench finder; do
  for mode in hybrid dense bm25; do
    uv run --no-sync loupe eval retrieval $ds --mode $mode --rerank none --limit 500
  done
  uv run --no-sync loupe eval retrieval $ds --mode hybrid --rerank minilm-l12 --limit 500
  uv run --no-sync loupe eval retrieval $ds --mode hybrid --rerank bge-base --limit 500
  uv run --no-sync loupe eval retrieval $ds --mode hybrid --rerank minilm-l12 --candidates 80 --limit 500
done
```
- **Output:** each run prints recall@1/3/5/10 and MRR, and saves a JSON file in `data/processed/retrieval/`.
- **Send back:** that folder zipped.

### T3 · Model pilots with your own keys (≈2–3 h, runs unattended)
Run models **different from Ayush's** (he runs `nim-nemotron-super`), so nothing is done twice:
```bash
for set in gold_num gold_calc gold_trick; do
  uv run --no-sync loupe eval run $set --split dev --limit 24 \
    --arm b0 --arm rag --arm react --arm loupe \
    --model oc-gemma4-31b --model nim-gpt-oss-20b --judge ministral-14b
done
uv run --no-sync loupe eval report
uv run --no-sync loupe eval export results-<yourname>-$(date +%Y%m%d).zip
```
- **Send back:** the export zip. Ayush runs `loupe eval import <zip>` and your rows join the same leaderboard.
- **If a model keeps failing** (rate limits), drop that `--model` and note it.

### T4 · Event-extraction blind test (≈30 min)
```bash
uv run --no-sync loupe extract eval-blind --model oc-gemma4-31b --scorer ministral-14b --limit 60 | tee extract-blind-gemma.txt
```
**Send back:** `extract-blind-gemma.txt` (precision, recall, F1, and precision by quality score).

### T5 · Human audit of the gold sets (≈1 h, no keys needed)
Open `data/gold/audit/audit_sample.csv`: 67 items, a seeded 5% sample of every gold set. For each row:
1. Open the source filing via the `source` accession on SEC EDGAR.
2. Check the `expected_answer`.
3. Fill `verdict` with `ok` or `wrong`, and add a short `note`.

**Send back:** the filled CSV. Its error rate goes into the report as the check on our AI-built data.

## Ground rules
- **Never run with `--final`** (the test split) until the team has signed off `docs/hypotheses.md`.
- **Don't commit** `.env`, `data/processed/` or `data/raw/`. They are git-ignored; send files directly.
- **Pull `main` before each task**, so results come from the same code version.
