# Models: what works for free (tested 2026-10-19)

Run `uv run loupe models check` to re-test. It sends three calls to each model: a plain reply, a tool call and a JSON-mode reply, printing each model's result as it goes.

## Live test with the team's keys

| Alias | Provider | Reply | Tools | JSON | Notes |
|---|---|---|---|---|---|
| `nim-nemotron-super` | NVIDIA NIM | ok | ok | ok | **Main model**: Nemotron 3 Super 120B MoE; up to 40 req/min, no daily cap published |
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

## Recommended set for experiments

| Role | Alias |
|---|---|
| Main / development | `nim-nemotron-super` |
| Google family | `oc-gemma4-31b`, with `nim-gemma-4-31b` as fallback |
| OpenAI open-weight, large / small | `oc-gpt-oss-120b`, `nim-gpt-oss-20b` |
| Judge (different family) | `ministral-14b` |
| FARE comparison (Gemini 2.5 Flash/Flash-Lite) | needs a free Gemini key |

## Gateway safeguards learned from the test
- **Timeout:** every call times out after 90 s, and a timeout is not retried. One stalled NIM request hung the first probe indefinitely.
- **Reasoning blocks:** `<think>…</think>` is removed from answers, so reasoning models are compared on their conclusions.
- **Probe budget:** the probe allows 600 output tokens, because reasoning models think before answering; 10 tokens made them look broken.
