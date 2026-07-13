"""
eval/paired_comparison.py

Consumes raw trial results (harness/request_runner.py output), runs every
generated snippet through the real correctness harness (eval/sim_runner.py),
and produces an aggregated per-config summary plus a same-prompt paired
diff (e.g. did fp16 pass but INT8 fail on the identical prompt?).

This is the analysis layer that turns raw JSON into the numbers that go in
VALIDATION_REPORT.md. It is fully testable against mock-server output --
see scripts/run_pilot_pipeline.py for an end-to-end proof, including a
deliberately injected regression to confirm this script actually detects it.
"""
import json
import statistics
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, asdict
import yaml
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.sim_runner import evaluate  # noqa: E402


@dataclass
class ConfigSummary:
    config_name: str
    n_trials: int
    n_passed: int
    pass_rate: float
    ttft_p50_s: float
    ttft_p95_s: float
    e2el_p50_s: float
    e2el_p95_s: float
    failure_categories: dict


def _percentile(values, pct):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def load_prompt_testbenches(manifest_path: str) -> dict:
    manifest = yaml.safe_load(Path(manifest_path).read_text())
    return {p["id"]: p["testbench_path"] for p in manifest["prompts"]}


def evaluate_raw_results(raw_results: list, testbench_map: dict) -> list:
    """Runs every trial's generated_text through the real eval harness."""
    enriched = []
    for r in raw_results:
        tb_path = testbench_map.get(r["prompt_id"])
        if not tb_path or not Path(tb_path).exists():
            r["eval_error"] = f"no testbench found for prompt {r['prompt_id']}"
            r["overall_passed"] = False
            r["failure_category"] = "harness_error"
            enriched.append(r)
            continue
        if not r["generated_text"].strip():
            r["overall_passed"] = False
            r["failure_category"] = "empty_generation"
            enriched.append(r)
            continue

        tb_code = Path(tb_path).read_text()
        result = evaluate(f"{r['prompt_id']}_{r['config_name']}_{r['trial_index']}",
                           r["generated_text"], tb_code)
        r["overall_passed"] = result.overall_passed
        r["failure_category"] = result.failure_category.value
        enriched.append(r)
    return enriched


def summarize_by_config(enriched_results: list) -> list:
    by_config = defaultdict(list)
    for r in enriched_results:
        by_config[r["config_name"]].append(r)

    summaries = []
    for config_name, rows in by_config.items():
        n = len(rows)
        n_passed = sum(1 for r in rows if r["overall_passed"])
        ttfts = [r["ttft_s"] for r in rows]
        e2els = [r["e2el_s"] for r in rows]
        cats = defaultdict(int)
        for r in rows:
            if not r["overall_passed"]:
                cats[r["failure_category"]] += 1

        summaries.append(ConfigSummary(
            config_name=config_name,
            n_trials=n,
            n_passed=n_passed,
            pass_rate=n_passed / n if n else 0.0,
            ttft_p50_s=_percentile(ttfts, 50),
            ttft_p95_s=_percentile(ttfts, 95),
            e2el_p50_s=_percentile(e2els, 50),
            e2el_p95_s=_percentile(e2els, 95),
            failure_categories=dict(cats),
        ))
    return summaries


def paired_diff(enriched_results: list, config_a: str, config_b: str) -> list:
    """For each (prompt_id, trial_index) present in both configs, report
    whether pass/fail status differs -- the specific comparison the
    proposal cares about (did quantization flip a pass to a fail?)."""
    by_key = defaultdict(dict)
    for r in enriched_results:
        key = (r["prompt_id"], r["trial_index"])
        by_key[key][r["config_name"]] = r

    diffs = []
    for key, configs in by_key.items():
        if config_a in configs and config_b in configs:
            a, b = configs[config_a], configs[config_b]
            if a["overall_passed"] != b["overall_passed"]:
                diffs.append({
                    "prompt_id": key[0],
                    "trial_index": key[1],
                    f"{config_a}_passed": a["overall_passed"],
                    f"{config_b}_passed": b["overall_passed"],
                    f"{config_a}_failure_category": a["failure_category"],
                    f"{config_b}_failure_category": b["failure_category"],
                })
    return diffs


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-results", required=True)
    parser.add_argument("--manifest", default="prompts/prompt_manifest.yaml")
    parser.add_argument("--output", default="results/processed/summary.json")
    parser.add_argument("--compare", nargs=2, metavar=("CONFIG_A", "CONFIG_B"),
                         help="Two config names to run a paired diff on")
    args = parser.parse_args()

    raw = json.loads(Path(args.raw_results).read_text())
    tb_map = load_prompt_testbenches(args.manifest)
    enriched = evaluate_raw_results(raw, tb_map)
    summaries = summarize_by_config(enriched)

    output = {
        "config_summaries": [asdict(s) for s in summaries],
        "enriched_results": enriched,
    }
    if args.compare:
        output["paired_diff"] = paired_diff(enriched, args.compare[0], args.compare[1])

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2, default=str))

    print(f"Wrote summary to {args.output}")
    for s in summaries:
        print(f"  {s.config_name}: {s.n_passed}/{s.n_trials} passed "
              f"({s.pass_rate:.0%}), TTFT p50={s.ttft_p50_s:.3f}s, "
              f"E2EL p50={s.e2el_p50_s:.3f}s, failures={s.failure_categories}")
    if args.compare:
        print(f"\nPaired diffs ({args.compare[0]} vs {args.compare[1]}): {len(output['paired_diff'])}")
        for d in output["paired_diff"]:
            print(f"  {d}")
