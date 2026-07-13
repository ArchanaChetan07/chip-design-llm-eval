"""
tests/test_harness.py
Fast unit tests, no GPU, no network beyond localhost mock server if run
manually. CI runs these against the real Icarus/Verilator install.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.sim_runner import evaluate, FailureCategory  # noqa: E402
from harness.metrics_collector import _parse_prometheus_text  # noqa: E402
from harness.cost_model import cost_for_cloud_call, cost_for_onprem_call  # noqa: E402


def test_known_good_adder_passes():
    good = Path("testbenches/arithmetic/adder_known_good.sv").read_text()
    tb = Path("testbenches/arithmetic/adder_tb.sv").read_text()
    result = evaluate("test_adder_good", good, tb)
    assert result.overall_passed is True
    assert result.failure_category == FailureCategory.NONE


def test_known_broken_adder_fails():
    broken = Path("testbenches/arithmetic/adder_known_broken.sv").read_text()
    tb = Path("testbenches/arithmetic/adder_tb.sv").read_text()
    result = evaluate("test_adder_broken", broken, tb)
    assert result.overall_passed is False
    assert result.failure_category == FailureCategory.SIMULATION_MISMATCH


def test_known_good_uart_passes():
    good = Path("testbenches/peripherals/uart_tx_known_good.sv").read_text()
    tb = Path("testbenches/peripherals/uart_tx_tb.sv").read_text()
    result = evaluate("test_uart_good", good, tb)
    assert result.overall_passed is True


def test_known_broken_uart_fails():
    broken = Path("testbenches/peripherals/uart_tx_known_broken.sv").read_text()
    tb = Path("testbenches/peripherals/uart_tx_tb.sv").read_text()
    result = evaluate("test_uart_broken", broken, tb)
    assert result.overall_passed is False


def test_prometheus_text_parsing():
    sample = (
        '# HELP x\n# TYPE x counter\n'
        'vllm_time_to_first_token_seconds_sum{model="mock"} 1.500000\n'
        'vllm_time_to_first_token_seconds_count{model="mock"} 3\n'
    )
    parsed = _parse_prometheus_text(sample)
    assert parsed["vllm_time_to_first_token_seconds_sum"] == 1.5
    assert parsed["vllm_time_to_first_token_seconds_count"] == 3


def test_cost_model_cloud():
    pricing = {"provider_a": {"prompt_per_1k": 0.003, "completion_per_1k": 0.015}}
    cost = cost_for_cloud_call(pricing, "provider_a", prompt_tokens=1000, completion_tokens=1000)
    assert abs(cost - (0.003 + 0.015)) < 1e-9


def test_cost_model_onprem():
    pricing = {"onprem": {"fp16": {"gpu_hour_rate": 1.0}}}
    cost = cost_for_onprem_call(pricing, "fp16", wall_seconds=3600)
    assert abs(cost - 1.0) < 1e-9
