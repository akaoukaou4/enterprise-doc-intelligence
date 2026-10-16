# Provider limits

> Free-tier limits change often and providers may stop publishing them. This file records what was **verified on our own account**, with the date. Re-check before relying on it, and always before an evaluation run that depends on a limit.

## Google Gemini API (Google AI Studio, free tier)

**Verified:** 2026-10-16, from the project owner's AI Studio rate-limit console (https://aistudio.google.com/rate-limit). Google's public rate-limit page does not list free-tier numbers for individual models; it points to this console.

The console shows `used / limit` for each model. The limits:

| Model | Requests/min (RPM) | Tokens/min (TPM) | Requests/day (RPD) | Use here |
|-------|--------------------|------------------|--------------------|----------|
| `gemini-3.5-flash-lite` | 15 | 250K | 500 | primary (D-28) |
| `gemini-3.1-flash-lite` | 15 | 250K | 500 | backup |
| `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash` | 5 | 250 (as shown) | 20 | Phase 7 experiment only |
| `gemini-2.5-flash-lite` | 10 | 250K | 20 | not used |
| `gemini-3.8-flash` TTS | 3 | 10K | 10 | not used |

Unchanged since 2026-10-02 for the two models in use. At the time of reading, `gemini-3.5-flash-lite` showed 6/15 requests this minute, 7.66K/250K tokens this minute and 15/500 requests today.

Notes:
- Quota is counted **per project, not per API key**, and the daily quota resets at **midnight Pacific time** (confirmed on Google's rate-limit page, 2026-10-16).
- Each `/ask` request, and each question of a full evaluation run, uses one LLM call. The daily budget is shared between development, evaluation and demos. Automated tests must use a fake LLM.
- A full evaluation run is 52 calls. With 20 requests per day on the larger Flash models, one full run does not fit in one day: compare a larger model on a subset of at most 20 questions, or spread the run over several days.
- Evaluation pacing (`MIN_SECONDS_BETWEEN_CALLS` in `app/evaluation/runner.py`) is one call every 5 seconds, 12 per minute, under the 15 per minute limit.
- Free-tier requests may be used by Google to improve its products. Use public/sample documents only while on the free tier (D-36).
- When a limit is hit, the 429 error body states the exact limit that was exceeded.

## Hugging Face (EmbeddingGemma, local model)

- Model: `google/embeddinggemma-300m` (gated: Gemma license accepted on the account; read-only token stored in `.env` as `HF_TOKEN`).
- Runs locally, so there is **no request quota**; the cost is RAM (about 1.2 to 1.3 GB) and disk (about 1.2 GB).
- Verified: question and document embeddings both have **768 dimensions**.
