# Chip-Design LLM Benchmark Suite

Benchmarks LLM-generated RTL correctness, latency, and cost across an
on-prem fp16 baseline, an on-prem INT8 (PagedKV-Fusion) config, and cloud
APIs. See `Chip_Design_LLM_Benchmark_Suite_Proposal.md` for the full
methodology and `GPU_Minimal_Build_Strategy.md` for why this repo is built
the way it is.

**Status: Stages 0–6 complete and verified. No GPU rented yet.**
Everything below has been built and actually run — not just written —
using a mock serving layer that mimics vLLM's API and Prometheus metrics.

## What's been proven so far (zero GPU cost)

| Component | Status | Proof |
|---|---|---|
| Repo scaffold + CI | ✅ | `.github/workflows/ci.yml` |
| Correctness harness (Icarus + Verilator) | ✅ verified | `python3 scripts/validate_testbenches.py` — passes known-good RTL, correctly fails known-broken RTL, for both `adder` and `uart_tx` |
| Unit tests | ✅ 7/7 passing | `pytest tests/` |
| Mock on-prem serving layer | ✅ | `serving/mock_vllm_server.py` — real Flask server, real HTTP, real Prometheus-format `/metrics` |
| Request orchestration (prompts × configs × trials) | ✅ | `harness/request_runner.py` — ran a real 2×2×3 matrix against two mock servers |
| Paired comparison (fp16 vs int8 regression detection) | ✅ verified | Deliberately injected a bug into the mock `int8` config; `eval/paired_comparison.py` correctly flagged all 3 pass→fail flips |
| Cost model | ✅ unit tested | `harness/cost_model.py` |
| Auto-generated report | ✅ | `scripts/generate_report.py` → `VALIDATION_REPORT.md`, regenerated from `results/processed/summary.json`, never hand-edited |
| Cloud API client (Anthropic) | ✅ real, wired into dispatch | `serving/cloud_clients/anthropic_client.py` — streaming-based TTFT, real SDK. **Not live-tested end-to-end**: no API key was available in the build sandbox. Error path (missing key) verified; happy path needs a real key to confirm before Stage 7. |
| Second cloud provider client | 🚧 template only | `serving/cloud_clients/template_client.py` — stub with TODOs, register in `CLOUD_CLIENT_REGISTRY` once written |
| Real vLLM fp16 + PagedKV-Fusion INT8 | ⏳ not started | requires GPU rental (Stage 7) |
| Prompt suite | 🟡 5 of ~40–60, all 4 categories covered | `adder`, `sat_counter`, `uart_tx`, `traffic_fsm`, `sync_fifo` — each with validated known-good/known-broken pairs |

## Quick start (no GPU required)

```bash
pip install -r requirements.txt
# System deps: iverilog, verilator (apt-get install iverilog verilator)

# 1. Prove the correctness harness is trustworthy
python3 scripts/validate_testbenches.py

# 2. Run unit tests
pytest tests/ -v

# 3. Start the mock serving layer (2 terminals, or background both)
python3 serving/mock_vllm_server.py --port 8000 --profile fp16 &
python3 serving/mock_vllm_server.py --port 8001 --profile int8 &

# 4. Run the full pilot pipeline against the mocks
python3 harness/request_runner.py \
  --manifest prompts/prompt_manifest.yaml \
  --configs serving/configs.example.json \
  --trials 3 --output-dir results/raw

LATEST=$(ls -t results/raw/*.json | head -1)
python3 eval/paired_comparison.py \
  --raw-results "$LATEST" \
  --manifest prompts/prompt_manifest.yaml \
  --output results/processed/summary.json \
  --compare fp16 int8

python3 scripts/generate_report.py --summary results/processed/summary.json
```

## Before renting a GPU (Stage 7)

1. **Set a real `ANTHROPIC_API_KEY`** and run
   `python3 serving/cloud_clients/anthropic_client.py` once as a live smoke
   test — this was written and structurally verified but never called with
   real credentials, since none existed in the build environment. Confirm
   TTFT/E2EL/token counts look sane before trusting it in the full run.
2. Expand `prompts/prompt_manifest.yaml` beyond the current 5 toward the
   full 40–60 prompt suite, each with a testbench validated the same way
   (write `_known_good.sv` + `_known_broken.sv` pairs, run
   `scripts/validate_testbenches.py`, confirm both directions pass).
3. Wire a second provider using `serving/cloud_clients/template_client.py`
   as a starting point, then register it in
   `harness/request_runner.py`'s `_load_cloud_client_registry()`.
4. Fill in `harness/pricing_snapshot.example.json` with real, dated pricing
   → save as `harness/pricing_snapshot.json`.
5. Swap `serving/configs.example.json` URLs to point at real vLLM instances
   once rented; `request_runner.py` needs zero code changes for this.
6. Run a short smoke test (2–3 real prompts, all configs) before committing
   to the full run — confirms real vLLM/PagedKV-Fusion and the real cloud
   client behave as expected before spending the full rental window.

## Repo structure

See `Chip_Design_LLM_Benchmark_Project_Plan.md` for the full structure
rationale and phase-by-phase task breakdown.
