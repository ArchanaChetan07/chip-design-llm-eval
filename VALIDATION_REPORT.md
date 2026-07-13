# Validation Report — Chip-Design LLM Benchmark Suite

*Auto-generated 2026-07-13T23:26:41.813294+00:00. Do not hand-edit -- regenerate from
`results/processed/summary.json` via `scripts/generate_report.py`.*

## Run Metadata
- Hardware: PLACEHOLDER (fill in exact rented GPU model)
- Model: PLACEHOLDER (fill in exact model + quantization)
- Prompt count: 0
- Trials per prompt per config: 0

## Correctness Summary

| Config | Passed | Total | Pass Rate | TTFT p50 (s) | TTFT p95 (s) | E2EL p50 (s) | E2EL p95 (s) |
|---|---|---|---|---|---|---|---|
| fp16 | 3 | 15 | 20% | 0.167 | 0.232 | 2.098 | 2.373 |
| int8 | 3 | 15 | 20% | 0.103 | 0.128 | 1.067 | 1.092 |

## Failure Category Breakdown

- **fp16**: syntax_error: 12
- **int8**: syntax_error: 12

## Paired Comparison (fp16 vs int8)

No pass/fail flips observed between fp16 and int8 on matched trials.

## Known Limitations of This Run

- This run used the mock serving layer, not real vLLM/PagedKV-Fusion or real cloud APIs -- numbers here are for pipeline validation only.
- Pilot prompt set (2 prompts) is far below the target 40-60 prompt suite.
