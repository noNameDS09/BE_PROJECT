# Data: what we have, where it is, how to rebuild it

All raw and processed data is git-ignored, so each person rebuilds it locally with the commands below.
Every download is cached and recorded with its source URL, so reruns are fast and results can be traced to exact files.

## 1. US company universe

`configs/companies_us.yaml` holds 25 companies. Decision D11 in `docs/decisions.md` records how they were chosen.

| Group | Companies | Why |
|---|---|---|
| FinanceBench overlap (15) | PEP, AMCR, JNJ, MMM, AMD, BBY, BA, AXP, MGM, PFE, ULTA, ADBE, JPM, VZ, CVS | 118 of the 150 open FinanceBench questions are about these companies |
| Risk events (10) | ADM, UNH, DBD, SHAK, SAH, ECHO, KR, RIG, CMP, BFH | FY2023–25 8-Ks with bankruptcy, cyber incident, debt acceleration, impairment, auditor change or restatement items |

- **Split:** 8 dev (MMM, AMD, ULTA, VZ, CVS, KR, CMP, BFH) and 17 test. Stratified by sector, seed 20261013.
- **Eligibility:** every company has at least 3 10-Ks and 9 10-Qs with a period of report in 2023-01-01..2025-12-31.

```bash
uv run loupe universe build   # resolve CIKs, check eligibility, assign split
```

## 2. SEC EDGAR corpus

| What | Source | Stored at |
|---|---|---|
| Filing index per company | `data.sec.gov/submissions` | `data/raw/sec/data.sec.gov/submissions/` |
| 10-K, 10-Q primary documents | EDGAR Archives | `data/raw/sec/www.sec.gov/Archives/edgar/data/<cik>/<accession>/` |
| 8-K primary documents + EX-99.1 earnings releases | EDGAR Archives | same |
| XBRL company facts (every reported number) | `data.sec.gov/api/xbrl/companyfacts` | `data/raw/sec/data.sec.gov/api/xbrl/companyfacts/` |
| Manifest (one row per filing: form, dates, 8-K items, files) | built by `loupe sec fetch` | `data/raw/sec/manifest.jsonl` |
| Coverage (listed vs fetched per company and form) | built by `loupe sec fetch` | `data/raw/sec/coverage.json` |
| Facts table (`facts`, view `facts_latest`) | built by `loupe sec facts` | `data/processed/loupe.duckdb` |

The window is periods of report from 2023-01-01 to 2025-12-31 for 10-K/10-Q, and filing dates in the same range for 8-K. Amendments (10-K/A, 8-K/A) are excluded.

```bash
# .env must contain SEC_USER_AGENT with a contact email (SEC returns 403 without one)
uv run loupe sec fetch        # filings + exhibits + XBRL (polite: 8 requests/s, cached)
uv run loupe sec facts        # XBRL -> DuckDB
uv run loupe ingest build     # clean text + sections + parse-quality report
```

### Parsing (clean text and sections)

`loupe ingest build` turns every fetched filing into a Document with clean text and its standard sections.

| Output | Path |
|---|---|
| One JSON line per document (company, form, accession, period, URL, sections with char offsets) | `data/processed/sec/documents.jsonl` |
| Clean text per document | `data/processed/sec/text/<doc_id>.txt` |
| Parse quality per form, plus every miss | `data/processed/sec/parse_report.json` |

**Cleaning steps:**
- Drop the hidden inline-XBRL header, scripts and styles.
- Turn each table row into one line, cells joined by ` | `.
- Normalise whitespace.

**Sections:**
- 10-K Items: 1, 1A, 7, 7A, 8 and so on.
- 10-Q Items, prefixed with their part: I-1, I-2, II-1A and so on.
- 8-K Items: 2.02, 4.02 and so on.
- Table-of-contents rows are recognised by their trailing page number and skipped.
- EX-99.1 earnings releases are stored as separate documents.

**Quality check:**
- 10-K: Items 1A, 7 and 8 found.
- 10-Q: Part I Items 1 and 2 found.
- 8-K: every item SEC lists for the filing found, except 9.01 (exhibit list).

## 3. Public evaluation datasets

Defined in `configs/datasets.yaml`. Each one is downloaded to `data/raw/public/<name>/` with a `MANIFEST.json` recording the URL, size, sha256, licence and retrieval time.

```bash
uv run loupe datasets list
uv run loupe datasets download                 # everything except deferred sets
uv run loupe datasets download docfinqa        # deferred: DocFinQA test split, 581 MB
```

| Name | Licence | Used for |
|---|---|---|
| financebench | CC-BY-NC-4.0 | Open 150 questions, the source PDFs they cite, and published GPT-4/Llama-2/Claude-2 results |
| finder | CC-BY-NC-4.0 | Retrieval against gold passages (10-K corpus) |
| failsafeqa | MIT | Hallucination and refusal robustness |
| secque | MIT (eval only) | Analyst-style comparison, ratio, risk and analysis questions |
| finance_agent_v1 / v2 | CC-BY-4.0 / MIT | Agent tool use on EDGAR (public splits) |
| finqa, tatqa | MIT, CC-BY-4.0 | Numeric reasoning, code-as-action |
| convfinqa | MIT | Multi-turn numeric chat |
| docfinqa | MIT | Long-document numeric QA (deferred) |
| indfin_bench, indiafinbench | CC-BY-NC-4.0, CC-BY-4.0 | India pilots |

Non-commercial licences are fine for this research project. Never redistribute the files.

## 4. Not yet collected

- **Daily prices** (for the price-forecast experiment and the Scenario tool): source not chosen yet.
- **Earnings-call transcripts:** skipped for the US (decision D10).
- **India data:** P6.
