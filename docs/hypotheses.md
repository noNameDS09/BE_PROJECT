# Pre-registration: Loupe-Orch v1 and hypotheses

Status: **DRAFT**. The team reviews it, then it is committed and tagged `prereg-v1` **before any experiment run**.
After the tag, this file is not edited. Changes go in `decisions.md` as dated deviations, and any analysis not listed here is reported as exploratory.

Full project plan: `docs/PLAN.md`.

## 1. Systems compared

Every arm uses the same model, retriever (index, embeddings, top-k), toolset and token cap per question.

| Arm | Method | Reference |
|---|---|---|
| B0 | Model alone, no retrieval, no tools | Baseline |
| O1 | Single-shot RAG: retrieve top-k, answer once | Standard RAG |
| O2 | ReAct: thought → tool → observation loop | Yao et al., ICLR 2023 |
| O3 | Plan-and-Execute (ReWOO style): plan all tool calls, execute, solve | Wang et al., ACL 2023; Xu et al. 2023 |
| O4 | Router → one specialist agent (single intent) | Chakraborty et al. (FARE), IEEE Access 14, 2026 |
| O5 | ReAct + Self-Refine critic (generate → critique → revise once) | Madaan et al., NeurIPS 2023 |
| Loupe | Loupe-Orch v1 (section 2) | This project |

**Crossed factor:** tools on (numbers come from code: XBRL lookup, calculator) vs tools off (the LLM reads and computes).

**Equal effort:** each arm's prompts get the same number of tuning rounds (3), on dev companies only.

## 2. Loupe-Orch v1 (fixed design)

1. **Router.** Multi-label intent classification into {lookup, calc, compare, event, trend, forecast, chart, open_analysis}, with company and period extraction.
2. **Planner.** Runs only if there is more than one intent, or a calc/compare/trend/chart intent. Writes a typed plan: a list of tool calls whose arguments may reference earlier results (ReWOO placeholders).
3. **Executors.** Run the plan. Retrieval is always filtered by the extracted company and period. Numbers come only from tools.
4. **Composer.** Writes the answer as claims. Each claim must reference evidence ids (chunk ids or fact ids) from the executor outputs.
5. **Verifier.**
   - (a) Code: every quoted span must appear in its chunk (fuzzy match ≥ 0.9). Every number in a claim must equal a tool output or a value in a cited chunk, within rounding.
   - (b) LLM critic: flags claims whose evidence does not support them.
   - Unsupported claims trigger one revision. Anything still unsupported is removed.
6. **Abstain.** If no claim survives, or the router finds no matching company or period in the corpus, the system says what is missing instead of answering.

Ablations (RQ3) remove one component at a time: router (always plan), planner (single step), tools, code verifier, critic, abstain rule.

## 3. Metrics

| Metric | Definition | Checked by |
|---|---|---|
| Numeric accuracy | Final number within 1% relative error of gold, or exact after the stated rounding; unit and period must match | Code |
| Hallucination rate | Share of answers with ≥1 unsupported claim. A claim is unsupported if its number matches no source value, its quote is not in the source, or the judge finds the cited evidence does not entail it | Code + judge |
| Trick-question accuracy | On Gold-Trick, share of answers that correctly refuse or correct the false premise | Code (label) + judge |
| Citation precision | Verified citations ÷ all citations | Code + judge |
| Retrieval recall@k | Gold evidence passage or page among the top-k retrieved | Code |
| Routing / plan accuracy | Intent-set exact match; tool-sequence match on Gold-Plan | Code |
| Event extraction | Precision, recall, F1 per event type; quote validity; precision by quality-score bin | Code |
| Cost | Tokens in/out, plus USD at the providers' listed paid prices (so free-tier runs are comparable) | Gateway log |
| Latency | Wall time per question | Gateway log |

The judge is an LLM from a different family than both the gold-data generator and the evaluated model where possible. Its agreement with the human audit sample is reported.

## 4. Hypotheses and decision rules

Main comparisons are on the **test** companies, on the core subset (about 300 questions), with each model analysed separately.

| Id | Hypothesis | Holds if |
|---|---|---|
| H1 | Loupe beats every other arm on numeric accuracy and hallucination rate, at a mean token cost no higher than O3's | For each arm X: the 95% CI of (Loupe − X) excludes 0 in the predicted direction on both metrics, and Loupe's mean tokens ≤ O3's |
| H2 | Of the Loupe components, removing the verifier increases hallucination rate the most | The verifier ablation has the largest increase, and its CI excludes 0 |
| H3 | Turning tools off lowers numeric accuracy more than any other single ablation | The tools-off ablation has the largest drop, and its CI excludes 0 |
| H4 | Loupe uses fewer tokens per question than O2 (ReAct) | The CI of the token ratio (Loupe / O2) lies below 1 |
| H5 | B0 hallucinates on company-specific questions far more than any retrieval arm | Hallucination rate of B0 − O1 > 0, CI excludes 0 |

**Statistics:**
- Company-cluster bootstrap (resample companies, 10,000 draws), 95% percentile CIs.
- Paired comparisons on the same questions.
- Holm correction across the arms within H1.
- Differences smaller than the minimum detectable effect, computed after the dev pilot, are reported as "not detectable with this sample", not as "no difference".

## 5. Data and splits

- 25 US companies (`configs/companies_us.yaml`), split by company into 8 dev / 17 test, stratified by sector, with a fixed seed.
- Test-company items are used only in final runs. The runner refuses test runs without `--final`, and every test run is logged.
- Public benchmarks run in bring-your-own-docs mode and are reported per dataset.
- Gold-data creation follows the protocol in `docs/PLAN.md` (code verification, cross-model check, 5% human audit).
