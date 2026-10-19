# Loupe API contract (backend ↔ Bench UI)

FastAPI serves everything under `/api`. The React app (`web/`) talks to the backend only through these endpoints. JSON field names are snake_case. All shapes are defined as Pydantic models in `src/loupe/api/models.py`; keep this file and that module in sync.

## Shared shapes

```jsonc
// Citation
{ "doc_id": "AMD_10-K_0000002488-25-000012", "chunk_id": "…:48211", "fact_id": null,
  "quote": null, "start_char": 48211, "end_char": 49380, "url": "https://www.sec.gov/…", "verified": null }

// Claim: one sentence of an answer
{ "text": "AMD revenue in fiscal 2024 was $25.8 billion [E1].", "citations": [Citation], "supported": true }
// supported: true = numbers/quotes match cited evidence; false = they don't; null = nothing checkable

// Evidence: one ledger item the answer can cite
{ "id": "E1", "kind": "chunk" | "fact" | "calc", "text": "…", "citation": Citation, "value": 25785000000 }

// TraceStep: one model call or tool call
{ "stage": "route" | "plan" | "step" | "tool" | "answer" | "verify" | "critique",
  "name": "nim-nemotron-super" | "search_filings" | …, "input": any, "output": any, "model": "…",
  "tokens_in": 812, "tokens_out": 96, "latency_ms": 1430, "cost_usd": 0.0 }

// Chart: a Plotly figure spec ({data, layout}) built only from verified numbers
{ "title": "AMD revenue FY2021–2025", "figure": { "data": [...], "layout": {...} }, "evidence_ids": ["E1","E2"] }

// RunResult
{ "run_id": "r_8f2c…", "arm": "react", "model": "nim-nemotron-super", "question": "…",
  "answer": { "text": "…", "claims": [Claim], "evidence": [Evidence], "trace": [TraceStep],
              "charts": [Chart], "abstained": false },
  "tokens": 4210, "latency_ms": 6230, "cost_usd": 0.0,
  "gold": { "answer": "$25,785 million", "correct": 1.0 } | null,   // when run on a dataset item
  "error": null }
```

## Endpoints

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | none | `{ "ok": true, "index": "c1200o150-bge-small", "models_with_keys": 3 }` |
| GET | `/api/config` | none | `{ "arms": [{ "name", "label", "description" }], "models": [{ "alias", "provider", "available" }], "datasets": [{ "name", "items", "kinds": [...] }], "companies": [{ "id", "name", "sector", "group", "split" }] }` |
| POST | `/api/runs` | `{ "question": "…", "arm": "react", "model": "nim-nemotron-super", "item_id": null }` | `RunResult` |
| POST | `/api/compare` | `{ "question": "…" \| null, "item_id": "financebench:…" \| null, "configs": [{ "arm", "model" }] }` (max 4 configs) | `{ "results": [RunResult] }` |
| GET | `/api/datasets/{name}/items` | `?offset=0&limit=50&split=dev&kind=numeric&q=text` | `{ "total": 150, "items": [EvalItem] }` |
| GET | `/api/datasets/{name}/items/{item_id}` | none | `EvalItem` |
| GET | `/api/results/leaderboard` | `?dataset=&split=&model=&arm=` | `{ "rows": [{ "arm", "model", "dataset", "n", "metrics": { "accuracy": { "mean", "lo", "hi" }, "hallucination_rate": {…}, "supported_rate": {…}, "abstain_rate": {…} }, "tokens": 0, "latency_ms": 0, "cost_usd": 0 }] }` |
| GET | `/api/results/stages` | `?dataset=&model=` | `{ "steps": [{ "label": "B0 closed book", "arm": "b0", "accuracy": {mean,lo,hi}, "hallucination_rate": {…} }] }`: the B0 → Loupe waterfall plus ablations |
| GET | `/api/results/runs` | `?dataset=&arm=&model=&correct=false&limit=50` | `{ "rows": [ResultRow] }`: drill-down, e.g. "show me B0's hallucinations" |
| GET | `/api/documents/{doc_id}` | `?start=&end=&context=600` | `{ "doc_id", "company_id", "form", "period_end", "url", "text", "highlight": [start, end] }`: citation viewer |
| POST | `/api/chat` | `{ "messages": [{ "role": "user" \| "assistant", "content": "…" }], "model": "…" }` | `RunResult` (arm `loupe`) |

`EvalItem` and `ResultRow` are defined in `src/loupe/eval/schema.py`.

## Errors

On failure the API returns HTTP 4xx/5xx with `{ "detail": "…" }`. A `RunResult` whose model call failed has `"error": "…"` and an empty answer, so the UI can still show the other configs in a comparison.
