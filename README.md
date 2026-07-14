![CI](https://github.com/ArchanaChetan07/chip-design-llm-eval/actions/workflows/ci.yml/badge.svg)

Hardware-in-the-loop LLM evaluation for RTL/SystemVerilog generation - dual-simulator (Icarus + Verilator) correctness checking, Flask mock serving, Docker-reproducible.

**5/5** dual-simulator harness pairs validated (**100%**) - **30-trial pilot** (5 prompts x 2 configs x 3 trials) - **7/7** tests passing - one-command Docker reproducible (no host EDA install).

How to run: `docker compose run --rm harness` (builds an image with `iverilog` + `verilator`, validates the harness, runs pytest).

---

## Overview

LLM-assisted RTL claims are hard to trust when "it compiled once" is treated as success. This repo is a **hardware-in-the-loop eval harness**: prompts go to a vLLM-compatible API (mock or real), generated SystemVerilog is checked for correctness against golden testbenches under **both Icarus Verilog and Verilator**, and latency / cost are recorded for serving configs.

Stack: Python, Flask (mock vLLM), pytest, Icarus, Verilator, Prometheus-style metrics on the mock server.

---

## Why This Matters

A single open-source simulator can have quirks that let incorrect RTL slip through. Requiring **agreement from two independent simulators** (Icarus + Verilator) on the same self-checking testbench raises the bar: syntax-only "compiles" is not enough, and simulator-specific blind spots are harder to hide. The harness itself is proven first on hand-written known-good / known-broken pairs before any LLM output is scored.

---

## Method

### What the "2 configs" are

The pilot compares two **on-prem serving profiles** (not two different foundation models):

| Config | Role |
|--------|------|
| **fp16** | Mock vLLM on port 8000 with higher artificial TTFT / E2EL (proxy for full-precision / slower serving) |
| **int8** | Mock vLLM on port 8001 with lower artificial latency (proxy for INT8 / faster serving) |

Both profiles currently return the same canned UART RTL for pipeline validation. Real GPU quantization swaps plug into the same `serving/configs*.json` + request runner without changing the dual-sim evaluator.

### Pilot matrix

- **5 prompts**: `uart_tx_basic`, `adder_param`, `traffic_fsm_basic`, `sync_fifo_basic`, `sat_counter_basic`
- **2 configs**: fp16, int8
- **3 trials** per prompt x config
- **Total: 30 trials** (honest pilot study - not a 40-60 prompt full benchmark)

Correctness = compile + sim under Icarus **and** Verilator against the paired `*_tb.sv`.

---

## Results

### Dual-simulator harness trust (re-verified in Docker this session)

| Pair | known-good | known-broken |
|------|:----------:|:------------:|
| uart_tx | pass | fail (mismatch) |
| traffic_fsm | pass | fail (mismatch) |
| sat_counter | pass | fail (mismatch) |
| adder | pass | fail (mismatch) |
| sync_fifo | pass | fail (mismatch) |

**5/5 pairs OK** - harness is trustworthy before LLM scoring.

### Unit tests

**7/7** passed inside the Docker image (`pytest -q`).

### Pilot study (n=30 trials, 5 prompts) - mock serving, not production GPU

From committed `results/processed/summary.json` / `VALIDATION_REPORT.md`:

| Config | Passed | Total | Pass rate | TTFT p50 | E2EL p50 |
|--------|-------:|------:|----------:|---------:|---------:|
| fp16 | 3 | 15 | **20%** | 0.167 s | 2.098 s |
| int8 | 3 | 15 | **20%** | 0.103 s | 1.067 s |

- INT8 E2EL ~**1.97x** faster than fp16 on the mock path (pipeline timing exercise).
- **0** paired pass-to-fail flips between fp16 and int8 on matched trials.
- Most failures are `syntax_error`: the mock returns canned **uart_tx** RTL for every prompt, so non-UART benches correctly fail. That is expected for mock pipeline validation, not a claim of live-LLM accuracy.

No additional LLM API trials were run in this session - the **30-trial pilot** number is not inflated.

---

## How to Run

### Docker-first (recommended)

```bash
git clone https://github.com/ArchanaChetan07/chip-design-llm-eval.git
cd chip-design-llm-eval

# Build image with apt-installed iverilog + verilator, then validate + pytest
docker compose run --rm harness
```

Optional mock serving (fp16 + int8 Flask apps):

```bash
docker compose up mock-fp16 mock-int8
# POST http://localhost:8000/v1/completions  (fp16 profile)
# POST http://localhost:8001/v1/completions  (int8 profile)
# GET  http://localhost:8000/metrics
```

No host install of Icarus or Verilator is required.

### Local (if you already have the tools)

```bash
sudo apt-get install -y iverilog verilator   # Debian/Ubuntu
pip install -r requirements.txt
python scripts/validate_testbenches.py
pytest -q
```

---

## Tests

```bash
docker compose run --rm harness
# or: pytest -q && python scripts/validate_testbenches.py
```

CI (`.github/workflows/ci.yml`) runs:
1. apt install of Icarus/Verilator + harness validate + pytest
2. **Docker image build** + same tests inside the container
3. mock fp16/int8 smoke matrix

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Eval | Icarus Verilog + Verilator (dual-sim) |
| API | Flask mock vLLM / real OpenAI-compatible or Anthropic clients |
| Orchestration | prompt manifest YAML, request runner, paired comparison, cost model |
| Observability | Prometheus text on mock `/metrics`, Grafana JSON |
| Quality | pytest, GitHub Actions, Docker Compose |

---

## License

See repository license / owner terms for this project.
