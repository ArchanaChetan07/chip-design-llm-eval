"""
scripts/generate_report.py

Generates VALIDATION_REPORT.md purely from results/processed/summary.json
and a small run-metadata file. Never hand-edit the report -- every number
must trace back to a script and a result file, per the proposal's core
integrity requirement.
"""
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone


TEMPLATE = """# Validation Report — Chip-Design LLM Benchmark Suite

*Auto-generated {generated_at}. Do not hand-edit -- regenerate from
`results/processed/summary.json` via `scripts/generate_report.py`.*

## Run Metadata
- Hardware: {hardware}
- Model: {model}
- Prompt count: {n_prompts}
- Trials per prompt per config: {n_trials}

## Correctness Summary

| Config | Passed | Total | Pass Rate | TTFT p50 (s) | TTFT p95 (s) | E2EL p50 (s) | E2EL p95 (s) |
|---|---|---|---|---|---|---|---|
{config_rows}

## Failure Category Breakdown

{failure_breakdown}

## Paired Comparison ({config_a} vs {config_b})

{paired_section}

## Known Limitations of This Run

{limitations}
"""


def build_config_rows(summaries):
    rows = []
    for s in summaries:
        rows.append(
            f"| {s['config_name']} | {s['n_passed']} | {s['n_trials']} | "
            f"{s['pass_rate']:.0%} | {s['ttft_p50_s']:.3f} | {s['ttft_p95_s']:.3f} | "
            f"{s['e2el_p50_s']:.3f} | {s['e2el_p95_s']:.3f} |"
        )
    return "\n".join(rows)


def build_failure_breakdown(summaries):
    lines = []
    for s in summaries:
        if s["failure_categories"]:
            cats = ", ".join(f"{k}: {v}" for k, v in s["failure_categories"].items())
            lines.append(f"- **{s['config_name']}**: {cats}")
        else:
            lines.append(f"- **{s['config_name']}**: no failures")
    return "\n".join(lines)


def build_paired_section(paired_diff, config_a, config_b):
    if not paired_diff:
        return f"No pass/fail flips observed between {config_a} and {config_b} on matched trials."
    lines = [f"{len(paired_diff)} same-prompt trial(s) where pass/fail status differed:\n"]
    for d in paired_diff:
        lines.append(
            f"- `{d['prompt_id']}` trial {d['trial_index']}: "
            f"{config_a}={'PASS' if d[f'{config_a}_passed'] else 'FAIL (' + d[f'{config_a}_failure_category'] + ')'}, "
            f"{config_b}={'PASS' if d[f'{config_b}_passed'] else 'FAIL (' + d[f'{config_b}_failure_category'] + ')'}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="results/processed/summary.json")
    parser.add_argument("--hardware", default="PLACEHOLDER (fill in exact rented GPU model)")
    parser.add_argument("--model", default="PLACEHOLDER (fill in exact model + quantization)")
    parser.add_argument("--n-prompts", type=int, default=0)
    parser.add_argument("--n-trials", type=int, default=0)
    parser.add_argument("--config-a", default="fp16")
    parser.add_argument("--config-b", default="int8")
    parser.add_argument("--limitations", default=(
        "- This run used the mock serving layer, not real vLLM/PagedKV-Fusion "
        "or real cloud APIs -- numbers here are for pipeline validation only.\n"
        "- Pilot prompt set (2 prompts) is far below the target 40-60 prompt suite."
    ))
    parser.add_argument("--output", default="VALIDATION_REPORT.md")
    args = parser.parse_args()

    data = json.loads(Path(args.summary).read_text())
    summaries = data["config_summaries"]
    paired = data.get("paired_diff", [])

    report = TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).isoformat(),
        hardware=args.hardware,
        model=args.model,
        n_prompts=args.n_prompts,
        n_trials=args.n_trials,
        config_rows=build_config_rows(summaries),
        failure_breakdown=build_failure_breakdown(summaries),
        config_a=args.config_a,
        config_b=args.config_b,
        paired_section=build_paired_section(paired, args.config_a, args.config_b),
        limitations=args.limitations,
    )

    Path(args.output).write_text(report)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
