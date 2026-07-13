"""
harness/metrics_collector.py

Scrapes a vLLM-compatible /metrics endpoint (real or mock) and extracts the
counters this benchmark cares about. Works identically against the mock
server (serving/mock_vllm_server.py) and a real vLLM instance, since both
expose the same metric names.
"""
import re
import requests
from dataclasses import dataclass


@dataclass
class ScrapedMetrics:
    requests_total: int
    ttft_avg_s: float
    tpot_avg_s: float
    e2el_avg_s: float
    generation_tokens_total: int
    prompt_tokens_total: int


_METRIC_LINE_RE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{[^}]*\}\s+([0-9.eE+-]+)$')


def _parse_prometheus_text(text: str) -> dict:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _METRIC_LINE_RE.match(line)
        if m:
            name, val = m.groups()
            values[name] = float(val)
    return values


def _safe_div(num, den):
    return num / den if den else 0.0


def scrape(metrics_url: str, timeout: float = 5.0) -> ScrapedMetrics:
    resp = requests.get(metrics_url, timeout=timeout)
    resp.raise_for_status()
    v = _parse_prometheus_text(resp.text)

    return ScrapedMetrics(
        requests_total=int(v.get("vllm_request_success_total", 0)),
        ttft_avg_s=_safe_div(v.get("vllm_time_to_first_token_seconds_sum", 0.0),
                              v.get("vllm_time_to_first_token_seconds_count", 0.0)),
        tpot_avg_s=_safe_div(v.get("vllm_time_per_output_token_seconds_sum", 0.0),
                              v.get("vllm_time_per_output_token_seconds_count", 0.0)),
        e2el_avg_s=_safe_div(v.get("vllm_e2e_request_latency_seconds_sum", 0.0),
                              v.get("vllm_e2e_request_latency_seconds_count", 0.0)),
        generation_tokens_total=int(v.get("vllm_generation_tokens_total", 0)),
        prompt_tokens_total=int(v.get("vllm_prompt_tokens_total", 0)),
    )


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/metrics"
    print(scrape(url))
