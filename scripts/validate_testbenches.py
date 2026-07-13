"""
scripts/validate_testbenches.py

Runs the eval harness against every known-good / known-broken RTL pair in
testbenches/**/*_known_good.sv and *_known_broken.sv, asserting the harness
gets the right answer in both directions. This MUST pass before any
LLM-generated RTL is ever evaluated -- it's the proof the correctness
measurement itself is trustworthy.

Exit code 0 = all checks passed. Non-zero = harness is not trustworthy yet,
do not proceed to benchmark execution.
"""
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.sim_runner import evaluate  # noqa: E402


def find_pairs():
    pairs = []
    for good_path in glob.glob("testbenches/**/*_known_good.sv", recursive=True):
        base = good_path.replace("_known_good.sv", "")
        broken_path = base + "_known_broken.sv"
        tb_path = base + "_tb.sv"
        if Path(broken_path).exists() and Path(tb_path).exists():
            pairs.append((base, good_path, broken_path, tb_path))
    return pairs


def main():
    pairs = find_pairs()
    if not pairs:
        print("NO known_good/known_broken/tb triples found -- nothing validated!")
        return 1

    all_ok = True
    for base, good_path, broken_path, tb_path in pairs:
        name = Path(base).name
        good_code = Path(good_path).read_text()
        broken_code = Path(broken_path).read_text()
        tb_code = Path(tb_path).read_text()

        good_result = evaluate(f"{name}_good", good_code, tb_code)
        broken_result = evaluate(f"{name}_broken", broken_code, tb_code)

        good_ok = good_result.overall_passed is True
        broken_ok = broken_result.overall_passed is False

        status = "OK" if (good_ok and broken_ok) else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"[{status}] {name}: known_good passed={good_result.overall_passed} "
              f"(expect True), known_broken passed={broken_result.overall_passed} "
              f"(expect False, category={broken_result.failure_category})")

    print()
    if all_ok:
        print(f"All {len(pairs)} harness validation pair(s) passed. "
              f"Eval harness is trustworthy.")
        return 0
    else:
        print("Harness validation FAILED. Do not proceed to benchmark execution "
              "until every pair passes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
