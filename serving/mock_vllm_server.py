"""
serving/mock_vllm_server.py

A local stand-in for vLLM's HTTP surface, used to build and fully debug the
harness/orchestration/metrics/cost pipeline WITHOUT renting a GPU.

Exposes:
  POST /v1/completions   - mimics vLLM's completion API, returns canned RTL
                            (optionally injected with a bug, and with
                            artificial latency to exercise TTFT/E2EL logic)
  GET  /metrics           - mimics vLLM's Prometheus exposition format with
                            the same metric names the real dashboard scrapes

Run: python3 serving/mock_vllm_server.py --port 8000 --profile fp16
Run: python3 serving/mock_vllm_server.py --port 8001 --profile int8
"""
import argparse
import random
import time
import threading
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Simple in-memory counters to fake Prometheus histograms.
_metrics_lock = threading.Lock()
_metrics = {
    "requests_total": 0,
    "ttft_sum": 0.0,
    "ttft_count": 0,
    "tpot_sum": 0.0,
    "tpot_count": 0,
    "e2el_sum": 0.0,
    "e2el_count": 0,
    "prompt_tokens_total": 0,
    "generation_tokens_total": 0,
}

CANNED_RTL = {
    "uart_tx": """module uart_tx (
    input  logic clk, rst_n, tx_start,
    input  logic [7:0] data,
    output logic tx, busy
);
    // canned mock output -- stands in for LLM generation during pipeline dev
    typedef enum logic [1:0] {IDLE, START, DATA, STOP} state_t;
    state_t state;
    logic [2:0] bit_idx;
    logic [7:0] shift_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE; tx <= 1'b1; busy <= 1'b0; bit_idx <= 0;
        end else begin
            case (state)
                IDLE: if (tx_start) begin
                    state <= START; busy <= 1'b1; shift_reg <= data;
                end
                START: begin tx <= 1'b0; state <= DATA; end
                DATA: begin
                    tx <= shift_reg[bit_idx];
                    if (bit_idx == 3'd7) state <= STOP;
                    else bit_idx <= bit_idx + 1;
                end
                STOP: begin tx <= 1'b1; busy <= 1'b0; state <= IDLE; bit_idx <= 0; end
            endcase
        end
    end
endmodule
""",
}

DEFAULT_MOCK_MODULE = "uart_tx"


def _profile_latency_params(profile: str):
    """Fake distinct latency characteristics per serving profile, so the
    metrics/cost pipeline has something realistic-shaped to aggregate."""
    if profile == "int8":
        return dict(ttft_mean=0.08, ttft_jitter=0.03, tok_per_s=140)
    if profile == "cloud_a":
        return dict(ttft_mean=0.25, ttft_jitter=0.10, tok_per_s=60)
    if profile == "cloud_b":
        return dict(ttft_mean=0.35, ttft_jitter=0.15, tok_per_s=45)
    # fp16 default
    return dict(ttft_mean=0.15, ttft_jitter=0.05, tok_per_s=70)


@app.route("/v1/completions", methods=["POST"])
def completions():
    body = request.get_json(force=True)
    prompt = body.get("prompt", "")
    inject_bug = body.get("_mock_inject_bug", False)  # test hook only
    profile = app.config["MOCK_PROFILE"]
    params = _profile_latency_params(profile)

    t_start = time.time()
    ttft = max(0.01, random.gauss(params["ttft_mean"], params["ttft_jitter"]))
    time.sleep(ttft)  # simulate time-to-first-token

    rtl = CANNED_RTL.get(DEFAULT_MOCK_MODULE, CANNED_RTL["uart_tx"])
    if inject_bug:
        # flip a condition to simulate a quantization-induced correctness bug
        rtl = rtl.replace("bit_idx == 3'd7", "bit_idx == 3'd6")

    n_tokens = len(rtl.split())
    gen_time = n_tokens / params["tok_per_s"]
    time.sleep(gen_time)

    e2el = time.time() - t_start
    tpot = gen_time / max(n_tokens, 1)

    with _metrics_lock:
        _metrics["requests_total"] += 1
        _metrics["ttft_sum"] += ttft
        _metrics["ttft_count"] += 1
        _metrics["tpot_sum"] += tpot
        _metrics["tpot_count"] += 1
        _metrics["e2el_sum"] += e2el
        _metrics["e2el_count"] += 1
        _metrics["prompt_tokens_total"] += len(prompt.split())
        _metrics["generation_tokens_total"] += n_tokens

    return jsonify({
        "id": "mock-cmpl-0",
        "choices": [{"text": rtl, "index": 0, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": n_tokens,
            "total_tokens": len(prompt.split()) + n_tokens,
        },
        "_mock_timing": {"ttft_s": ttft, "e2el_s": e2el, "tpot_s": tpot},
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    """Mimics vLLM's Prometheus exposition format (subset of real metric
    names) so the harness's metrics_collector.py can be built/tested against
    the real wire format before ever touching a real vLLM instance."""
    with _metrics_lock:
        m = dict(_metrics)
    lines = [
        "# HELP vllm_request_success_total Total successful requests",
        "# TYPE vllm_request_success_total counter",
        f'vllm_request_success_total{{model="mock"}} {m["requests_total"]}',
        "# HELP vllm_time_to_first_token_seconds_sum TTFT sum",
        "# TYPE vllm_time_to_first_token_seconds_sum counter",
        f'vllm_time_to_first_token_seconds_sum{{model="mock"}} {m["ttft_sum"]:.6f}',
        "# HELP vllm_time_to_first_token_seconds_count TTFT count",
        "# TYPE vllm_time_to_first_token_seconds_count counter",
        f'vllm_time_to_first_token_seconds_count{{model="mock"}} {m["ttft_count"]}',
        "# HELP vllm_time_per_output_token_seconds_sum TPOT sum",
        "# TYPE vllm_time_per_output_token_seconds_sum counter",
        f'vllm_time_per_output_token_seconds_sum{{model="mock"}} {m["tpot_sum"]:.6f}',
        "# HELP vllm_time_per_output_token_seconds_count TPOT count",
        "# TYPE vllm_time_per_output_token_seconds_count counter",
        f'vllm_time_per_output_token_seconds_count{{model="mock"}} {m["tpot_count"]}',
        "# HELP vllm_e2e_request_latency_seconds_sum E2EL sum",
        "# TYPE vllm_e2e_request_latency_seconds_sum counter",
        f'vllm_e2e_request_latency_seconds_sum{{model="mock"}} {m["e2el_sum"]:.6f}',
        "# HELP vllm_e2e_request_latency_seconds_count E2EL count",
        "# TYPE vllm_e2e_request_latency_seconds_count counter",
        f'vllm_e2e_request_latency_seconds_count{{model="mock"}} {m["e2el_count"]}',
        "# HELP vllm_generation_tokens_total Total generated tokens",
        "# TYPE vllm_generation_tokens_total counter",
        f'vllm_generation_tokens_total{{model="mock"}} {m["generation_tokens_total"]}',
        "# HELP vllm_prompt_tokens_total Total prompt tokens",
        "# TYPE vllm_prompt_tokens_total counter",
        f'vllm_prompt_tokens_total{{model="mock"}} {m["prompt_tokens_total"]}',
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "profile": app.config["MOCK_PROFILE"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--profile", type=str, default="fp16",
                         choices=["fp16", "int8", "cloud_a", "cloud_b"])
    args = parser.parse_args()
    app.config["MOCK_PROFILE"] = args.profile
    app.run(host="127.0.0.1", port=args.port)
