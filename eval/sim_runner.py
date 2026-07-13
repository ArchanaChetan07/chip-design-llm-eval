"""
eval/sim_runner.py

Compiles and simulates a generated RTL module against its paired reference
testbench, using BOTH Icarus Verilog and Verilator. Returns a structured
pass/fail result with failure categorization.

This is the correctness-evaluation core of the benchmark suite. It must be
100% trustworthy before any LLM output is ever run through it -- see
scripts/validate_testbenches.py, which runs this same code against
hand-written known-correct and known-broken RTL.
"""

import subprocess
import tempfile
import os
import shutil
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class FailureCategory(str, Enum):
    NONE = "none"                       # passed
    SYNTAX_ERROR = "syntax_error"
    SIMULATION_MISMATCH = "simulation_mismatch"
    TIMEOUT = "timeout"
    NON_SYNTHESIZABLE = "non_synthesizable"     # heuristic flag, not guaranteed
    SIMULATOR_DISAGREEMENT = "simulator_disagreement"  # icarus and verilator disagree
    HARNESS_ERROR = "harness_error"     # something went wrong in our tooling, not the RTL


@dataclass
class SimResult:
    simulator: str                 # "icarus" | "verilator"
    passed: bool
    failure_category: FailureCategory
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0


@dataclass
class EvalResult:
    prompt_id: str
    icarus: Optional[SimResult] = None
    verilator: Optional[SimResult] = None
    overall_passed: bool = False
    failure_category: FailureCategory = FailureCategory.NONE
    simulator_disagreement: bool = False

    def to_dict(self):
        d = asdict(self)
        return d


TIMEOUT_SECONDS = 10


def _run_cmd(cmd, cwd, timeout=TIMEOUT_SECONDS):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        return -1, e.stdout or "", (e.stderr or "") + "\n[TIMEOUT]", True


def _classify_failure(returncode: int, stdout: str, stderr: str, timed_out: bool) -> FailureCategory:
    if timed_out:
        return FailureCategory.TIMEOUT
    combined = (stdout + stderr).lower()
    # Simulation self-checking testbenches should print a clear marker.
    # Convention used in this repo's testbenches: "SIM_PASS" / "SIM_FAIL".
    if "sim_fail" in combined:
        return FailureCategory.SIMULATION_MISMATCH
    if returncode != 0:
        if any(tok in combined for tok in ["syntax error", "parse error", "unexpected"]):
            return FailureCategory.SYNTAX_ERROR
        if any(tok in combined for tok in ["not synthesizable", "unsupported construct"]):
            return FailureCategory.NON_SYNTHESIZABLE
        return FailureCategory.SYNTAX_ERROR  # default bucket for non-zero exit w/o clearer signal
    if "sim_pass" not in combined:
        # Compiled and ran but never asserted pass -- treat as mismatch, not a silent pass.
        return FailureCategory.SIMULATION_MISMATCH
    return FailureCategory.NONE


def run_icarus(dut_path: str, tb_path: str, workdir: str) -> SimResult:
    import time
    t0 = time.time()
    vvp_out = os.path.join(workdir, "sim.vvp")
    rc, out, err, timed_out = _run_cmd(
        ["iverilog", "-g2012", "-o", vvp_out, tb_path, dut_path], cwd=workdir
    )
    if rc != 0 or timed_out:
        cat = _classify_failure(rc, out, err, timed_out)
        return SimResult("icarus", False, cat, out, err, time.time() - t0)

    rc, out, err, timed_out = _run_cmd(["vvp", vvp_out], cwd=workdir)
    cat = _classify_failure(rc, out, err, timed_out)
    passed = cat == FailureCategory.NONE
    return SimResult("icarus", passed, cat, out, err, time.time() - t0)


def run_verilator(dut_path: str, tb_path: str, workdir: str) -> SimResult:
    import time
    t0 = time.time()
    # --binary builds and runs in one step; --timing supports delay-based TBs.
    rc, out, err, timed_out = _run_cmd(
        ["verilator", "--binary", "--timing", "-Wno-fatal", "-sv",
         "--top-module", "tb", "-o", "sim_verilator",
         tb_path, dut_path],
        cwd=workdir,
    )
    if rc != 0 or timed_out:
        cat = _classify_failure(rc, out, err, timed_out)
        return SimResult("verilator", False, cat, out, err, time.time() - t0)

    binpath = os.path.join(workdir, "obj_dir", "sim_verilator")
    if not os.path.exists(binpath):
        return SimResult("verilator", False, FailureCategory.HARNESS_ERROR,
                          out, err + "\n[binary not produced]", time.time() - t0)

    rc, out2, err2, timed_out = _run_cmd([binpath], cwd=workdir)
    cat = _classify_failure(rc, out2, err2, timed_out)
    passed = cat == FailureCategory.NONE
    return SimResult("verilator", passed, cat, out + out2, err + err2, time.time() - t0)


def evaluate(prompt_id: str, dut_code: str, testbench_code: str,
             run_verilator_too: bool = True) -> EvalResult:
    """
    Core entry point. Writes dut+tb to a scratch dir, runs both simulators,
    and returns a combined structured result.
    """
    with tempfile.TemporaryDirectory(prefix=f"simeval_{prompt_id}_") as workdir:
        dut_path = os.path.join(workdir, "dut.sv")
        tb_path = os.path.join(workdir, "tb.sv")
        Path(dut_path).write_text(dut_code)
        Path(tb_path).write_text(testbench_code)

        icarus_result = run_icarus(dut_path, tb_path, workdir)
        verilator_result = None
        if run_verilator_too:
            # verilator needs its own workdir (obj_dir clashes if reused)
            vworkdir = os.path.join(workdir, "verilator_run")
            os.makedirs(vworkdir, exist_ok=True)
            shutil.copy(dut_path, os.path.join(vworkdir, "dut.sv"))
            shutil.copy(tb_path, os.path.join(vworkdir, "tb.sv"))
            verilator_result = run_verilator(
                os.path.join(vworkdir, "dut.sv"),
                os.path.join(vworkdir, "tb.sv"),
                vworkdir,
            )

        overall_passed = icarus_result.passed and (
            verilator_result.passed if verilator_result else True
        )

        disagreement = (
            verilator_result is not None
            and icarus_result.passed != verilator_result.passed
        )

        if disagreement:
            failure_category = FailureCategory.SIMULATOR_DISAGREEMENT
        elif not overall_passed:
            failure_category = (
                icarus_result.failure_category
                if not icarus_result.passed
                else verilator_result.failure_category
            )
        else:
            failure_category = FailureCategory.NONE

        return EvalResult(
            prompt_id=prompt_id,
            icarus=icarus_result,
            verilator=verilator_result,
            overall_passed=overall_passed,
            failure_category=failure_category,
            simulator_disagreement=disagreement,
        )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("usage: sim_runner.py <prompt_id> <dut.sv> <tb.sv>")
        sys.exit(1)
    result = evaluate(sys.argv[1], Path(sys.argv[2]).read_text(), Path(sys.argv[3]).read_text())
    print(json.dumps(result.to_dict(), indent=2, default=str))
