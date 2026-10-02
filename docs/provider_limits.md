# Provider limits

> Free-tier limits change often and providers may stop publishing them. This file records what was **verified on our own account**, with the date. Re-check before relying on it (especially at the start of Phase 6).

## Google Gemini API (Google AI Studio, free tier)

**Verified:** 2026-10-02, from the project owner's AI Studio rate-limit console.

| Model | Requests/min (RPM) | Tokens/min (TPM) | Requests/day (RPD) | Test call |
|-------|--------------------|------------------|--------------------|-----------|
| `gemini-3.5-flash-lite` (primary) | 15 | 250K | 500 | Successful |
| `gemini-3.1-flash-lite` (backup) | 15 | 250K | 500 | Successful |

Notes:
- Quota is counted **per project, not per API key**, and the daily quota resets at **midnight Pacific time**.
- Each `/ask` request uses one LLM call, so the daily budget is shared between development, evaluation and demos. Automated tests must use a fake LLM.
- Free-tier requests may be used by Google to improve its products. Use public/sample documents only while on the free tier.
- Full Flash models were reported by a third party (2026-09-02) to have a much lower free daily limit (about 20 requests/day), which is why Flash-Lite is the primary choice.
- When a limit is hit, the 429 error body states the exact limit that was exceeded.

## Hugging Face (EmbeddingGemma, local model)

- Model: `google/embeddinggemma-300m` (gated: Gemma license accepted on the account; read-only token stored in `.env` as `HF_TOKEN`).
- Runs locally, so there is **no request quota**; the cost is RAM (about 1.2 to 1.3 GB) and disk (about 1.2 GB).
- Verified: question and document embeddings both have **768 dimensions**.
