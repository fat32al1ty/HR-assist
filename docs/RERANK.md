# Rerank cascade (Phase 2.5)

Two optional stages that polish the top of the match list after the
scoring + MMR + tier cascade. Both are off by default — flip them on
with env vars once you're ready to pay the cost.

```
recall → filter → role_family_gate → domain_gate → scoring →
  dedupe → cross_encoder_rerank → diversify → tier → llm_rerank → augment
```

## Stage 2.5a — Cross-encoder rerank

Local model, no API calls, no per-request cost beyond GPU/CPU time.

| Setting                       | Default                     | Notes                                      |
| ----------------------------- | --------------------------- | ------------------------------------------ |
| `RERANK_ENABLED`              | `false`                     | Master flag. When off, the stage is a no-op. |
| `RERANK_MODEL_NAME`           | `BAAI/bge-reranker-v2-m3`   | Multilingual, ~568 MB, Apache-2.0.         |
| `RERANK_CANDIDATE_LIMIT`      | `50`                        | Only the top-K by hybrid_score get reranked. |
| `RERANK_BLEND_WEIGHT`         | `0.6`                       | `hybrid = (1-w) * hybrid + w * sigmoid(ce_logit)`. |
| `RERANK_BATCH_SIZE`           | `16`                        | Forward-pass batch on the cross-encoder.   |

Logits come back unbounded so we sigmoid them before blending —
keeps the blend linear in `[0, 1]`. Failure to load or run the model
is caught: the stage logs `rerank_fallback` in diagnostics and the
pre-rerank ordering is preserved.

First call pays the model-load cost (~1–2s cold); subsequent calls
hit the process-local singleton. The image is built with CPU-only
torch — see `backend/Dockerfile`.

## Stage 2.5b — LLM rerank + Russian reasons

Pays OpenAI for a top-K rerank and a short Russian explanation per
card. Disk-cached for 24 h keyed on `(resume_id, sorted vacancy_ids,
model)`. Budget-gated so a user's daily spend can't run away.

| Setting                         | Default        | Notes                                    |
| ------------------------------- | -------------- | ---------------------------------------- |
| `LLM_RERANK_ENABLED`            | `false`        | Master flag.                             |
| `LLM_RERANK_MODEL`              | `gpt-4o-mini`  | Pick a cheap model — this is structured output, not reasoning. |
| `LLM_RERANK_TOP_K`              | `20`           | Number of candidates sent to the LLM.    |
| `LLM_RERANK_BUDGET_FLOOR_USD`   | `0.05`         | Skip the call if daily headroom < floor. |
| `LLM_RERANK_CACHE_TTL_HOURS`    | `24`           | Disk cache TTL; stale entries unlink on read. |

Output schema (strict JSON):

```json
{
  "ranked": [
    {"vacancy_id": 123, "position": 1, "reason_ru": "…", "confidence": 0.87}
  ]
}
```

The reason is surfaced in the public match-result dict as
`profile.reason_ru` and rendered in the frontend as the "Почему
показали" block. `rerank_skipped=true` lands on the profile when the
LLM call was bypassed (budget, failure, missing API key) — the UI
hides the block.

### Budget guard

`llm_rerank._budget_ok` reads
`repositories.user_daily_spend.get_daily_spend_usd` for the request's
`user_id` and requires `(daily_budget_usd - spend) >= budget_floor_usd`.
If the repo lookup fails, we default to *allow* — we'd rather serve
reasons than fail the request.

### Cost model

For the default `gpt-4o-mini` at the listed rates (input $0.15 /
output $0.60 per 1M), 20 compact vacancy rows + resume profile ~= 2k
input / 400 output tokens. Per-call ceiling ~= $0.0006, amortised
across the 24 h cache.

## Rolling it out

1. Ship with both flags `false` (current state).
2. On a staging env, flip `RERANK_ENABLED=true` first — pure latency +
   CPU impact, no external spend. Watch NDCG + p95 matching latency.
3. Then flip `LLM_RERANK_ENABLED=true`. Watch daily spend per user
   and `llm_rerank_cache_hit` vs `llm_rerank_applied` in diagnostics.
4. If the cache hit rate is low, the user is churning vacancy sets
   faster than the 24 h TTL — consider raising the TTL before cutting
   top-K.

## Tests

- `backend/tests/test_cross_encoder_rerank.py` — mocks
  `app.services.rerank_model.predict_pairs`; covers flag-off,
  ordering flip, blend formula, fallback, head-only mutation, sigmoid
  bounds.
- `backend/tests/test_llm_rerank.py` — mocks the OpenAI client and
  the disk cache; covers flag-off, missing key, cache hit/miss,
  budget skip, LLM failure, `_splice_head` preservation of dropped +
  tail candidates, unranked leftovers.
