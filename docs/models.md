# Models: what works (tested 2026-11-01)

Run `uv run loupe models check` to re-test. It sends three calls to each model: a plain reply, a tool call and a JSON-mode reply, printing each model's result as it goes.

## Live test, 2026-11-01

### API keys

| Key | Result |
|---|---|
| `GEMINI_API_KEY` | Works: the first Gemini results on this bench |
| `CLAUDE_API_KEY_v2` | Works: 13 model ids listed, 4 tested below. The balance can't be read through the API; check it in the Console |
| `CLAUDE_API_KEY_v1` | Valid, but calls fail with "credit balance is too low" |
| `CURSOR_API_KEY` | Valid, but not usable on the bench: it runs Cursor's cloud agents, it is not a raw model API |

### Usable models

| Alias | Provider | Reply | Tools | JSON | Notes |
|---|---|---|---|---|---|
| `gemini-3.6-flash` | Google AI Studio | ok | ok | ok | Current Flash |
| `gemini-flash` | Google AI Studio | ok | ok | ok | Gemini 2.5 Flash, FARE's family; about 250 requests/day |
| `gemini-3.1-flash-lite` | Google AI Studio | ok | ok | ok | Newer Flash-Lite |
| `gemini-flash-lite` | Google AI Studio | ok | ok | ok | Gemini 2.5 Flash-Lite, FARE's family; about 1,000 requests/day |
| `oc-gemma4-31b` | Ollama Cloud | ok | ok | ok | Free plan: 1 request at a time, weekly usage cap |
| `oc-gpt-oss-120b` | Ollama Cloud | ok | ok | ok | Same limits |
| `or-nemotron-lightning` | OpenRouter | ok | ok | ok | Small and fast |
| `ministral-14b` | Mistral | ok | ok | ok | **Judge only**: it can't also be a tested model |
| `groq-gpt-oss-120b`, `groq-qwen-27b` | Groq | ok | ok | ok | Short calls only: 7–8K input tokens/min as of 2026-10-19 |
| `nim-nemotron-ultra` | NVIDIA NIM | ok | ok | **failed** | Used in pilot 3. Re-check before long runs |
| `or-nemotron-ultra` | OpenRouter | ok | ok | **failed** | `APIError` on the JSON call |

Gemini 3.x logs a warning that `temperature`, `top_p` and `top_k` are planned for removal. Gemini 2.5 was listed for retirement on Vertex on 2026-10-20, with no date on the Developer API we use. It still answers, so run it early.

### Not usable today

| Alias | Provider | Result |
|---|---|---|
| `nim-nemotron-super` | NVIDIA NIM | Not found (retired 2026-10-20) |
| `or-nemotron-super` | OpenRouter | No longer free (retired upstream) |
| `nim-gemma-4-31b` | NVIDIA NIM | Tool call timed out |
| `nim-gpt-oss-20b` | NVIDIA NIM | Timed out |
| `or-gemma-4-31b` | OpenRouter | Rate-limited on tools and JSON |
| `mistral-medium`, `mistral-small` | Mistral | Rate-limited |

## Claude (paid, not in the registry yet)

These were tested by calling the API directly, because `configs/models.yaml` has no Claude entries yet. Only a tool call was tested; `loupe models check` has not been run on them.

| Model id | Tool call | Price per 1M tokens, in / out | One full run, estimated |
|---|---|---|---|
| `claude-haiku-5-5` | ok | $0.10 / $0.50 | ~$3 |
| `claude-sonnet-5-5` | ok | $2 / $10 | ~$60 |
| `claude-opus-5-5` | ok | $4 / $20 | ~$120 |
| `claude-fable-5-1` | ok | $10 / $50 | ~$300 |

Prices are as cached on 2026-10-06. The estimate assumes 300 questions × 7 methods, about 56K tokens per question across the methods (from pilot token use) and an 80/20 input/output split: about 17M tokens. Nothing has run on Claude yet, and thinking would add to this.

**Needed before Claude can run in the bench:**
1. Add Claude to `configs/models.yaml` and `PROVIDER_KEYS` in `src/loupe/llm/registry.py`, using `CLAUDE_API_KEY_v2`.
2. Pin the official address, `https://api.anthropic.com`, because a shell may set its own `ANTHROPIC_BASE_URL`.
3. Stop sending `temperature` to Claude. The gateway sends `temperature=0` on every call, and all four models reject it with a 400. Log this in `docs/decisions.md` as a protocol deviation.
4. Don't force `tool_choice` on Opus 5.5, Sonnet 5.5 or Fable 5.1: the API docs say it returns a 400, so use `auto`. Thinking also can't be turned off on Opus 5.5.

**Gold data:** the model that writes gold data must never be a tested model. If Claude is tested, Opus or Fable writes gold and only Haiku and Sonnet are tested. We disclose the shared family and cross-check with Gemini.

## Proposed set for experiments

| Role | Alias |
|---|---|
| Full comparison | `oc-gemma4-31b`, `oc-gpt-oss-120b`, `gemini-3.6-flash` |
| FARE comparison (Gemini 2.5) | `gemini-flash` |
| Top-end check, on Loupe and the two best baselines only | `claude-haiku-5-5`, `claude-sonnet-5-5` |
| Judge (different family) | `ministral-14b` |

**Capacity:** one full run is roughly 8,000 calls (estimate). At about 250 requests/day, `gemini-flash` would take about a month on one key, so teammates' keys matter here.

## Live test, 2026-10-19

| Alias | Provider | Reply | Tools | JSON | Notes |
|---|---|---|---|---|---|
| `nim-nemotron-super` | NVIDIA NIM | ok | ok | ok | Main model at the time: Nemotron 3 Super 120B MoE; up to 40 req/min, no daily cap published |
| `nim-gemma-4-31b` | NVIDIA NIM | ok | ok | ok | Slow (~50 s per call) |
| `nim-gpt-oss-20b` | NVIDIA NIM | ok | ok | ok | Small/mid model |
| `oc-gemma4-31b` | Ollama Cloud | ok | ok | ok | Fast (1–3 s). Free plan: 1 request at a time, weekly usage cap |
| `oc-gpt-oss-120b` | Ollama Cloud | ok | ok | ok | Same limits |
| `ministral-14b` | Mistral | ok | ok | ok | Mistral family is used by no generator, so it is the **judge** |
| `groq-gpt-oss-120b`, `groq-qwen-27b` | Groq | ok | ok | ok | Input capped at 7–8K tokens/min: a RAG prompt (~11K) is rejected. Short calls only |
| `or-nemotron-super` | OpenRouter | ok | ok | ok | 50 free requests/day (1,000/day after a one-time $10 top-up) |
| `mistral-medium`, `mistral-small` | Mistral | rate-limited | | | Free-tier request limit; retry later |
| `or-gemma-4-31b` | OpenRouter | busy | | | Free provider at capacity |
| Gemini (4 aliases) | Google AI Studio | not tested | | | No `GEMINI_API_KEY` yet (free, no card: aistudio.google.com) |

**Update 2026-10-20, 19:24 IST:** `nim-nemotron-super` started returning `404 Function not found for account` partway through pilot 3, although the model is still listed in NIM's catalogue. Re-test with `loupe models check --only nim-nemotron-super` before long runs. Fall back to `oc-gemma4-31b`. Per-model usage so far: [`experiments/llm-usage-by-model.csv`](../experiments/llm-usage-by-model.csv).

**Removed after testing:**
- Llama-Nemotron 70B and Kimi K2.6 on NIM: 404, not available to the account.
- Groq Llama 3.1 8B: no longer offered.
- DeepSeek V4.1 Flash and GLM-5.3 Flash on NIM: time out after 90 s.
- Mistral Large, and the DeepSeek, Kimi and Mistral Large models on Ollama Cloud: not included in the free plan.

## First real comparisons

| Question | Plain LLM (B0) | Loupe |
|---|---|---|
| AMD FY2024 revenue and growth (Groq Qwen 27B) | Looped and contradicted itself; 0 verified claims | $25.785B, +13.69% from $22.680B; 2/2 verified; 1,887 tokens |
| "Why did Shake Shack file for bankruptcy in 2024?" (Gemma 4 31B) | Rejected the premise | Rejected the premise, from evidence |
| Diebold 8-K risk events + revenue chart (Gemma 4 31B) | — | All events with dates, chart from XBRL, FY2023 correctly missing; 3,478 tokens vs ReAct's 10,856 |

## Gateway safeguards learned from the test
- **Timeout:** every call times out after 90 s, and a timeout is not retried. One stalled NIM request hung the first probe indefinitely.
- **Reasoning blocks:** `<think>…</think>` is removed from answers, so reasoning models are compared on their conclusions.
- **Probe budget:** the probe allows 600 output tokens, because reasoning models think before answering; 10 tokens made them look broken.
