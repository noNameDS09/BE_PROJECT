# Loupe-Gold: deterministic sets (dataset card)

Our own evaluation sets for the 25-company US universe (`configs/companies_us.yaml`).
Everything here is built **by code, with no LLM**, from SEC XBRL facts and EDGAR filing
metadata, and every item is re-checked by `gold verify`.
LLM-assisted sets (Gold-Compare, Gold-Chart, Gold-Multiturn, event quotes) come later and
follow the creation protocol in `docs/PLAN.md`.

Each file holds one `EvalItem` per line (`src/loupe/eval/schema.py`).

## Sets

| File | Kind | Items | Dev | Test | What it tests |
|---|---|---|---|---|---|
| `gold_num.jsonl` | numeric | 300 | 96 | 204 | Exact single values (12 metrics, FY2023–25 and quarters) |
| `gold_calc.jsonl` | numeric | 150 | 48 | 102 | Values computed from 2–3 facts (growth, margins, ratios, FCF, CAGR) |
| `gold_trick.jsonl` | refusal | 125 | 47 | 78 | False premises, future periods, missing metrics, wrong company, outside coverage |
| `gold_event_labels.jsonl` | event | 555 | 206 | 349 | Which 8-K items a filing reports |
| `gold_plan.jsonl` | plan | 199 | 67 | 132 | Router intents and planner tool sequence |

**Split.** Every item takes the dev/test split of its company (8 dev / 17 test companies).
Multi-company items only pair companies from the same split.
Items that name no company in the universe get a seeded draw with P(dev) = 8/25.
This covers outside-universe tricks and sector-level plan questions with mixed splits.
Test items are for final runs only (`docs/hypotheses.md`).

## How each set is built

All randomness comes from `random.Random("20261013:<set>:<key>")`, so a rebuild on the same
data gives byte-identical files.

### gold_num (Gold-Num)

- **Metrics (12):** revenue, net income, operating income, gross profit, diluted EPS, operating cash flow, capex, total assets, total liabilities, equity, cash and long-term debt.
- **Slots per company:** 12. That is 3 fiscal-year and 1 quarterly question for each of FY2023, FY2024 and FY2025.
- **Metric choice:** each slot takes the least-used metric that `FactsStore.get` resolves.
- **Totals:** 225 fiscal-year and 75 quarterly items, 100 per year and 12 per company.
- **Derived Q4:** 10 quarterly items are Q4 values computed as FY minus 9-month YTD. They are marked with `meta.derived = "FY - 9M YTD"`. Derived Q4 is never used for EPS.
- **Phrasing:** several templates per metric type (flow, balance, EPS).
- **Units:** the question always states the unit (USD millions, USD billions or USD per share).
- **Labels:** the question names the concept that was actually tagged. For example, American Express gets "total net revenue (net of interest expense)".
- **Dates:** non-calendar fiscal years and quarters carry their period-end date.
- **Answer:** `answer_value` is the exact XBRL value in base units (USD or USD/share), with tolerance 1%.

### gold_calc (Gold-Calc)

- **Calculations (6 per company):**
  - YoY growth of revenue, net income or operating cash flow
  - gross margin (from gross profit, or from revenue minus cost of revenue)
  - operating margin and net margin
  - current ratio
  - debt-to-equity (long-term debt / equity)
  - free cash flow (operating cash flow minus capex)
  - 2-year revenue CAGR (FY2023→FY2025)
- **Skipped cases:** undefined values are left out. These are growth across a loss (sign change), negative equity and division by zero.
- **Stored with each item:** `meta.calc` (the function name), `meta.formula`, and `meta.inputs` with full provenance for every input fact.
- **Answer value:** `answer_value` is the unrounded result.
- **Tolerance:** 1% relative, widened to the rounding the question asks for. That is ±0.05 percentage points for percentages and ±0.005 for ratios.

### gold_trick (Gold-Trick)

`answer` describes the expected behaviour (refuse or correct). `meta.reason` names the trick, and each premise is verified against the data.

| reason | n | Built from | Verified by |
|---|---|---|---|
| `future_period` | 25 | FY2027/FY2028 questions | FactsStore has no fact, and the fiscal year ends after the data cutoff (2026-10-13) |
| `unreported_metric` | 25 | A curated list of line items a business does not present (banks: operating income and gross profit; retailers: R&D; software: inventory, ...) | FactsStore resolves nothing for FY2023–25 **and** the facts table has zero rows for any of the metric's concepts for that company |
| `false_premise_1_03` / `_4_02` / `_1_05` / `_4_01` | 10 / 10 / 6 / 4 | "Why did X file for bankruptcy / restate / suffer a breach / change auditor ..." | No 8-K from that company in the corpus window (2023–2025) reports that item, per `raw/sec/manifest.jsonl` |
| `wrong_company_event` | 20 | A real risk 8-K (1.03, 1.05, 4.01, 4.02, plus a sample of 2.04 and 2.06) attributed to another company from the same split | The accession belongs to the true filer and carries the item; the named company never filed that item |
| `outside_universe` | 15 | Well-known companies not among the 25 (Apple, Microsoft, ...) | Ticker not in the universe |
| `false_number` | 10 | Another company's real FY revenue stated as this company's | Both values match FactsStore and differ by more than 25% |

### gold_event_labels (Gold-Event, labels only)

- **Which filings:** every 8-K in the manifest whose items include any of 1.01, 1.03, 1.05, 2.01, 2.04, 2.05, 2.06, 3.01, 4.01, 4.02, 5.02 or 8.01. There are 555 such filings.
- **Labels:** every item code in the filing except 9.01 (the exhibit list), with SEC's official item names. They are stored in `meta.items` and `meta.event_items`, and as one `evidence` row per item.
- **Documents:** the parsed document ids (`<TICKER>_8-K_<accession>`, plus `_ex1` press releases).
- **Item frequency:** 8.01 ×260, 5.02 ×216, 1.01 ×96, 2.04 ×9, 2.06 ×9, 2.01 ×6, 2.05 ×5, 4.02 ×4, 1.03 ×3, 3.01 ×3, 4.01 ×2, 1.05 ×2.
- **Quotes:** `meta.quotes` is empty. Verbatim quotes and extracted fields will be added by an LLM pass and checked against the text by code.

### gold_plan (Gold-Plan)

- **Templates:** 31, filled with real companies and years. They yield 124 single-intent items and 75 multi-intent items; `category` records which.
- **Intents:** lookup, calc, compare, event, trend, forecast, chart and open_analysis.
- **Expected tools:**
  - `expected_tools` uses the full planned toolset: search_filings, get_financial_metric, calculate, list_companies, compare_companies, make_chart, forecast_metric and list_events.
  - `meta.expected_tools_minimal` is the same plan using only today's four tools.
- **No hidden tricks:** every metric a template needs resolves in FactsStore for the companies and years named, so no plan item is secretly a trick question.

## Provenance fields

| Set | Fields |
|---|---|
| Numeric items | `meta.fact` (gold_num) or `meta.inputs.*` (gold_calc): company, metric, fiscal_year, period, value, unit, XBRL concept, period_start/end, accession, form, filed date, EDGAR folder URL, derived. `evidence` repeats the accession and links the parsed doc id when that filing is in the corpus. |
| Trick and event items | accession, filing date, item code and name, URL, and the window or cutoff checked |

## Rebuild and verify

Point `DATA_DIR` at the folder holding `raw/sec/manifest.jsonl`, `processed/loupe.duckdb` (opened read-only) and `processed/sec/documents.jsonl`.

```bash
export DATA_DIR=/path/to/Loupe/data
uv run python -m loupe.datasets.cli gold build     # all five sets -> data/gold/
uv run python -m loupe.datasets.cli gold verify    # recompute everything; must report 0
# once registered in the main CLI: uv run loupe evalsets gold build / verify
```

`gold verify` does the following and exits 1 on any mismatch:
- re-queries every fact and checks value, concept, accession and period end;
- recomputes every calculation from fresh inputs;
- re-checks every trick premise;
- checks event labels against the manifest and parsed documents, and that no qualifying 8-K is missing;
- checks plan labels against the allowed intents and tools.

## Known limitations

- **Values are "latest filed".** FactsStore reads `facts_latest`, so a FY2023 value may come from the comparative column of the FY2025 10-K. That includes any recast. The accession in the provenance is the filing that supplied the number, which is not always the period's own 10-K.
- **Fiscal labels follow each company's convention** (decision D15).
  - Best Buy's "fiscal 2023" ended January 28, 2023.
  - Ulta's and Kroger's labels are one year lower than Best Buy's for the same period.
  - Questions state the period-end date wherever the year is not a calendar year.
- **Some quarters are missing.** FactsStore finds quarter ends at 91-day steps back from the year end. Companies with 16-week first quarters (Kroger) or a 12/12/12/16-week calendar (PepsiCo) therefore get fewer quarterly items, and PepsiCo has no derived Q4. They are missing, not wrong.
- **`unreported_metric` depends on a curated allow-list.** A company could present a line item under a custom extension concept, and SEC companyfacts omit extensions. The allow-list keeps to absences explained by the business model.
- **Invented-event premises are checked only inside the corpus window** (8-Ks filed 2023-01-01..2025-12-31). Question years stay inside that window.
- **Plan labels are template-defined.** They have one canonical tool order, whereas real plans can differ in order. Scorers should compare intent sets and tool sets, or use the minimal variant.
- **Only step 3 of the creation protocol has been applied.** That step is code verification. The cross-model check and the 5% human audit (protocol steps 4–5) are still to do.
