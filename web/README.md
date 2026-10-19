# Loupe Bench (web)

The React front end for Loupe: compare orchestration arms side by side, read benchmark results,
browse datasets and stored runs, and chat with the Loupe orchestration. It talks to the FastAPI
backend only through the endpoints in [`docs/api.md`](../docs/api.md).

Vite + React 18 + TypeScript (strict), react-router, Plotly (lazy-loaded), plain CSS with variables.

## Run

Needs Node 22.

```bash
cd web
npm install

npm run dev:mock     # no backend needed: every call is served from src/mocks/ (http://localhost:5173)
npm run dev          # real backend: proxies /api to http://localhost:8000 (override with LOUPE_BACKEND=…)

npm run typecheck    # tsc --noEmit
npm test             # vitest (pure logic + mock client)
npm run build        # typecheck + production build into web/dist/
npm run preview      # serve the built app
```

Environment variables (see `.env.example`): `VITE_API_BASE` (default `/api`), `VITE_MOCK=1`
(mock mode), `VITE_MOCK_DELAY` (mock latency in ms, default 350).

## Pages

| Route | Page | Endpoints |
|---|---|---|
| `/` | **Compare**: a typed question or a dataset item × up to 4 (arm, model) configs, answers in columns. `/?item=<item_id>` preselects an item. | `/config`, `/datasets/{name}/items`, `/datasets/{name}/items/{id}`, `POST /compare`, `/documents/{doc_id}` |
| `/leaderboard` | Sortable table of `mean [lo, hi]` metrics + grouped bar chart with CI error bars | `/results/leaderboard` |
| `/stages` | B0 → Loupe accuracy waterfall (hallucination rate as a line) + steps/ablations table | `/results/stages` |
| `/datasets` | Dataset cards, paginated/filterable item table, item detail with "Run in Compare" | `/config`, `/datasets/{name}/items` |
| `/runs` | Drill-down over stored ResultRows with filters; click a row for the answer | `/results/runs` |
| `/chat` | Chat with the full history sent each turn; answers render like Compare | `POST /chat` |

Filters live in the URL query string, so views can be linked.

## Layout

```
web/
├── index.html, vite.config.ts, tsconfig.json, package.json, .env.example
└── src/
    ├── main.tsx, App.tsx          # router, sidebar, theme toggle, API health dot
    ├── api/
    │   ├── types.ts               # the contract, mirrored from the backend (see below)
    │   ├── client.ts              # ApiClient interface, HTTP client, ApiError, mock switch
    │   └── client.test.ts
    ├── components/
    │   ├── AnswerView.tsx         # shared answer renderer: claims, [E#] chips, charts, evidence, trace
    │   ├── RunCard.tsx            # one Compare column: stats strip, gold + correct badge, error card
    │   ├── CitationDrawer.tsx     # right drawer: evidence + /documents passage with the span highlighted
    │   ├── citationContext.ts     # open/close API used by chips
    │   ├── EvidenceList.tsx, TraceTimeline.tsx, Collapsible.tsx
    │   ├── MetricCell.tsx         # mean [lo, hi] + mini interval bar
    │   ├── ConfigPicker.tsx       # arm × model rows (max 4) and ModelSelect
    │   ├── PlotlyChart.tsx        # lazy wrapper; PlotlyInner.tsx holds plotly.js (separate chunk)
    │   ├── Feedback.tsx           # EmptyState, ErrorBanner, InfoBanner, skeletons, Spinner
    │   ├── Filters.tsx, Icon.tsx
    ├── lib/
    │   ├── citations.ts           # [E#] parsing, claim ↔ answer-text segmentation, verdicts
    │   ├── format.ts              # metric/number formatting, correctness mapping
    │   ├── useAsync.ts, useConfig.ts, theme.ts, arms.ts, examples.ts
    │   └── *.test.ts
    ├── mocks/                     # VITE_MOCK=1 only (not in the production bundle)
    │   ├── index.ts               # createMockClient(): same shapes, filters and errors as the API
    │   ├── scenarios.ts           # mock orchestrator: (question | item, arm, model) → RunResult
    │   ├── builders.ts            # constructors, deterministic hashing, per-arm trace shapes
    │   ├── fixtures/              # config (25 companies, arms, models), items, documents, results
    │   └── mockClient.test.ts
    ├── pages/                     # ComparePage, LeaderboardPage, StagesPage, DatasetsPage, RunsPage, ChatPage
    └── styles/global.css          # tokens (light/dark), layout, components
```

## Types ↔ backend contract

`src/api/types.ts` mirrors the backend field-for-field in snake_case:

| TypeScript | Source |
|---|---|
| `Citation`, `Claim`, `TraceStep`, `Answer` | `src/loupe/core/schemas.py` |
| `EvalDoc`, `GoldEvidence`, `EvalItem`, `ResultRow`, `Kind` | `src/loupe/eval/schema.py` |
| `Evidence`, `Chart`, `RunResult`, `Gold`, request/response bodies, `Metric`, `LeaderboardRow`, `StageStep`, `DocumentResponse` | `docs/api.md` |

Rules: Pydantic fields with defaults are always serialised, so they are required in TS;
`X | None` is `X | null`; `datetime` is an ISO 8601 string. `Answer.evidence` and
`Answer.charts` are `list[dict]` in Python; the UI types them as `Evidence[]` and `Chart[]`
exactly as `docs/api.md` describes.

### Points the backend should match

These were not pinned down by the contract; the UI assumes:

1. **Rates are fractions in [0, 1]** (`Metric.mean/lo/hi`, `supported_rate`,
   `retrieval_recall`); the UI converts to percent. Any `Metric` field may be `null`.
2. **Leaderboard `tokens`, `latency_ms`, `cost_usd` are means per run**, not totals.
3. **`/documents/{doc_id}`: `text` is the window around the cited span (± `context` chars) and
   `highlight` is `[start, end]` relative to that `text`**, not to the full document. The drawer
   only fetches when the citation has `doc_id` and `start_char`; facts and calcs show their
   record and the SEC link instead.
4. **`StageStep.kind`** (optional extension): `"step"` rows form the waterfall in order;
   `"ablation"` rows appear only in the table (Δ vs. the last step). Absent means `"step"`.
5. **`ResultRow.meta.answer`** (optional extension): if a stored row includes the full `Answer`,
   Runs shows claims/evidence/trace; otherwise only the answer text.
6. **`/results/runs?correct=`**: `true` means `correct >= 0.5`, `false` means `correct < 0.5`;
   rows with `correct = null` match neither. Gold/row `correct` between 0 and 1 (judge score)
   shows as "partial" when ≥ 0.5.
7. **Claims are verbatim sentences of `Answer.text`** (whitespace may differ). The UI highlights
   them in place; if any claim is not found in the text it lists the claims instead.
8. **Evidence ids** are `E<n>`; markers may be `[E1]`, `[E1][E2]` or `[E1, E2]`. A marker whose id
   is missing from `Answer.evidence` renders as a dashed chip.
9. **`POST /compare` with an `item_id`** sends `question: null`; `gold` is set only for item runs.
   A failing config returns a `RunResult` with `error` and an empty answer (the column shows an
   error card); request-level failures use HTTP errors with `{ "detail": … }` (FastAPI's list form
   is flattened).
10. **`/api/chat`** gets the whole history; assistant turns are sent as `answer.text`.
11. TraceStep `stage` is treated as an open string; known values get coloured dots
    (`route`, `plan`, `step`, `tool`, `answer`/`compose`, `verify`, `critique`).

## Mock data

Mock mode is for building and demoing the UI before the backend exists. Fixtures use the real
25 tickers and model aliases. Hand-written scenarios: AMD FY2024 revenue (B0 hallucinates a number,
Loupe is fully supported with a chart, the FARE router mis-computes growth), a Shake Shack
Chapter 11 false-premise question (Loupe abstains, ReAct falls for it) and the UnitedHealth
cyberattack 8-K (one deliberately unchecked claim). Numeric dataset items get generated answers;
`nim-llama-70b` and `ollama-llama-8b` always fail, to show error cards. **Figures and passages are
illustrative, not verified data, and the leaderboard/stage numbers are invented.**
