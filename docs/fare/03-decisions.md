# FARE Decisions Log

Every place where Loupe departs from, or fills a gap in, the FARE paper, and every scope decision that affects results.
One row per decision. **Could change results?** = yes means the choice must also appear as an ablation or a stated limitation.
After the protocol freeze (target 11 Oct 2026), changes are added as new rows with a date; old rows are never edited.

Companion docs: `01-extraction-sheet.md` (what the paper says), `02-claims.md` (what we test), Loupe Research Protocol v0.1 (https://claude.ai/artifact/Uj5RgQTqQoALuA2ZsyAHFf).

## Decided

| Id | Date | Decision | Options considered | Reason | Could change results? |
|---|---|---|---|---|---|
| D1 | 2026-09-29 | Data = SEC EDGAR filings (10-K, 10-Q, 8-K) by CIK. FARE's transcripts are not reconstructed. | Rebuild transcript set; filings | Transcripts are not freely redistributable; filings are public and structured. | Yes: tested claims are "FARE's conclusions on filings", not its numbers. |
| D3 | 2026-09-29 | Hosted LLM APIs only, behind one gateway. | Local GPU; hosted | No GPU budget; reproducible access. | Yes for latency (C2, C3): not comparable with FARE's T4 numbers. |
| D4 | 2026-09-29 | Investment → Thesis Check, Simulation → Scenario; no buy/hold/sell. | Keep advisory agents | Advice is out of scope for the project. | Yes: IRAS and EAS are adapted (see O5). |
| D5 | 2026-09-29 | Judges are versioned; systems are compared only under the same judge version. | Single judge | FARE's judges were never validated. | Yes: RQ3. |
| D9 | 2026-10-03 | Universe = 19 companies from the data on `atharva-patil-plan` that meet the inclusion rule (≥3 10-K and ≥6 10-Q for FY2023–2025, US domestic filer). Listed in `configs/universe.yaml`. Replaces "team's 25" in plan v2. | All 50 files; top up with FARE's companies; re-pick | The 50 files are the first 50 CIKs of `companyfacts.zip`; 31 cannot support FY2023–25 experiments. Team chose the eligible 19, fixed. | Yes: declared biases (old registrants, financials-heavy, no software/retail/banks). |
| D10 | 2026-10-03 | From `atharva-patil-plan`, only `Data/` is used. Copied unchanged to `data/raw/companyfacts/` (git-ignored) with `_SHA256SUMS` and `_PROVENANCE.txt`. No code is merged. | Merge branch; salvage tools | Branch answers from XBRL with keyword rules and no LLM; its benchmark is self-graded. | No. |
| D11 | 2026-10-03 | Guide approved: Phase R (SEC replication) first, then Phase I (India). | — | — | No. |
| D12 | 2026-10-03 | Gemini models are called through the Gemini Developer API, not Vertex. All Gemini 2.5 generations are run and cached first. | Vertex AI | Vertex lists 2.5 Flash / Flash-Lite retirement on 2026-10-20; the Developer API shows no shutdown date (both checked 2026-10-03). | Yes if 2.5 is retired before runs finish: successor results reported separately (O3). |
| D13 | 2026-10-03 | Dev/test split by company, stratified by size band, seed 20261005: dev = ABT, AXP, AFL, HWM, SWKS, ALX; test = the other 13. All tuning on dev only. | Split by query; split by period | A query split leaks company-specific prompt tuning into test. | Yes: fewer clusters in test (13) widen CIs. |
| D14 | 2026-10-03 | EDGAR requests send a User-Agent with a team contact email, at most 10 requests per second. | — | data.sec.gov returned 403 without one (2026-10-03). | No. |

## Open (answer before the protocol freeze)

| Id | Question | Recommendation | Owner |
|---|---|---|---|
| O1 | Tone critic: inference-time loop or evaluation only? (p. 67368 says both) | Inference-time loop as v0; "critic off" as an RQ4 ablation. | Stream B |
| O2 | Daily price source for Scenario | Free source with a stable licence, downloaded once, checksummed. | Stream A |
| O3 | Successor model if Gemini 2.5 is retired | Gemini 3.1 Flash-Lite on the same queries, overlapping with 2.5 runs. | Stream D |
| O4 | Gemini 2.5 Flash thinking budget | 0 for main runs; default budget as one ablation. | Stream B |
| O5 | Adapted metrics for Thesis Check and Scenario | Drop IRAS recommendation-correctness and risk-profile terms, renormalise; keep CODS. | Stream C |
| O6 | Adopt RQ5 (memorisation: before/after model cutoff, anonymisation probe)? | Yes. | All |
| O7 | Batch size for batch-wise chunk reading (FARE: held constant, value not given) | Choose on dev, record value. | Stream B |
| O8 | Contact email for the EDGAR User-Agent | A team or college address, not a personal one. | Stream A |
