# Chip-Design LLM Benchmark Suite — Project Plan & Requirements
*Companion execution doc to the proposal. Author: Archana Chetan. July 2026.*

---

## 1. Prerequisites & Requirements

### 1.1 Hardware
| Item | Minimum | Notes |
|---|---|---|
| On-prem GPU | 1x NVIDIA GPU, ≥16GB VRAM (24GB+ preferred) | Consumer GPU acceptable if disclosed per proposal's honest-hardware rule. RTX 3090/4090, A5000, or better. |
| Host RAM | ≥32GB | For model loading + concurrent trial orchestration |
| Disk | ≥200GB free | Model weights (multiple quantization levels) + logs + generated RTL corpus |
| Network | Stable outbound HTTPS | For cloud API calls; avoid running cloud trials on flaky connections (skews TTFT) |

### 1.2 Software / Accounts
- **OS:** Ubuntu 22.04/24.04 (or WSL2 equivalent)
- **CUDA:** 12.x, matching your existing PagedKV-Fusion build
- **Python:** 3.10 or 3.11 (pin one; vLLM is picky about versions)
- **vLLM:** version already validated with PagedKV-Fusion kernels
- **Icarus Verilog** (`iverilog`) and **Verilator** — both, for cross-checking
- **Docker** (optional but recommended for reproducible harness environment)
- **Prometheus + Grafana** — reused from LLM-Inference-Benchmarking-Dashboard; confirm dashboard JSON still imports cleanly
- **NVIDIA DCGM** — confirm exporter is running and scraped by Prometheus
- **Cloud API keys** — at least 2 providers (e.g., Anthropic, OpenAI, or others offering coding-capable models). Set up billing alerts before running trials — repeated-trial benchmarking burns tokens fast.
- **GitHub repo** with Actions enabled (CI/CD)
- **Git LFS** (optional) if model weights or generated corpora get large

### 1.3 Model Selection
- One open-weight coding-capable model you can serve at both fp16 and INT8 (e.g., a Qwen2.5-Coder, DeepSeek-Coder, or CodeLlama variant sized to fit your VRAM budget at fp16)
- Confirm the model is licensed for this use (check license terms — some coding models restrict commercial/benchmarking redistribution of outputs)
- Decide up front whether cloud APIs use the *same* underlying model family (cleaner comparison) or deliberately different flagship models (more realistic "which service would I actually pick" framing) — this is a methodology decision to state explicitly in the report

### 1.4 Knowledge/Skill Prerequisites
- Comfort writing Verilog/SystemVerilog testbenches (self-checking, not just waveform-eyeballing)
- Familiarity with vLLM's `/metrics` Prometheus format
- Basic stats: percentiles, confidence intervals, paired difference tests (a paired t-test or Wilcoxon signed-rank is likely enough given your sample size)

---

## 2. Repository Structure

```
chip-llm-bench/
├── README.md
├── VALIDATION_REPORT.md              # final output, generated not hand-written
├── requirements.txt / pyproject.toml
├── .github/workflows/
│   ├── ci.yml                        # lint + unit tests on every push
│   └── harness-smoke-test.yml        # tiny end-to-end run on 1-2 prompts, no real GPU cost
├── prompts/
│   ├── fsm/
│   ├── peripherals/
│   ├── arithmetic/
│   ├── interface_adapters/
│   └── prompt_manifest.yaml          # id, category, prompt text, ref testbench path, difficulty tag
├── testbenches/
│   └── <mirrors prompts/ structure>  # one reference tb per prompt, pre-validated against known-good RTL
├── serving/
│   ├── vllm_fp16_config.yaml
│   ├── vllm_int8_pagedkv_config.yaml
│   └── cloud_clients/
│       ├── provider_a_client.py
│       └── provider_b_client.py
├── harness/
│   ├── request_runner.py             # fixed-concurrency, repeated-trial orchestration
│   ├── metrics_collector.py          # TTFT/TPOT/ITL/E2EL scraping + client-side timing fallback
│   └── cost_model.py                 # $/module, $/1K tokens from pricing + GPU-hour cost
├── eval/
│   ├── lint.py                       # basic syntax/style pass
│   ├── sim_runner.py                 # invokes Icarus + Verilator, captures pass/fail + failure category
│   └── paired_comparison.py          # fp16 vs INT8 vs cloud, same-prompt diffing
├── dashboards/
│   └── grafana_dashboard.json
├── results/
│   ├── raw/                          # per-run JSON, timestamped, untouched
│   └── processed/                    # aggregated tables feeding the report
└── scripts/
    ├── validate_testbenches.py       # sanity-check harness against known-correct RTL first
    └── snapshot_pricing.py           # captures cloud pricing pages as of benchmark date
```

---

## 3. Initial Setup Checklist

- [ ] Provision/confirm GPU access; record exact GPU model, VRAM, driver version, CUDA version
- [ ] Create repo, set up `.github/workflows/ci.yml` (pytest + lint on push)
- [ ] Install and pin Python deps; commit `requirements.txt`
- [ ] Install Icarus Verilog + Verilator; verify both with a trivial known-good module (e.g., a 2-bit counter) before writing a single prompt
- [ ] Stand up vLLM fp16 baseline; confirm `/metrics` endpoint is scraping into Prometheus
- [ ] Stand up vLLM + PagedKV-Fusion INT8 config; confirm kernel loads correctly and throughput roughly matches your prior ~21x benchmark on a smoke test
- [ ] Import/confirm Grafana dashboard from LLM-Inference-Benchmarking-Dashboard renders with new data source
- [ ] Get API keys for 2 cloud providers; do a $0.01 smoke-test call from each to confirm auth + client timing instrumentation works
- [ ] Set billing alerts on cloud accounts
- [ ] Write and commit `scripts/validate_testbenches.py` workflow — this must pass before any LLM output is evaluated, or the correctness numbers are meaningless
- [ ] Snapshot cloud pricing pages (`scripts/snapshot_pricing.py`) and commit as of a fixed date

---

## 4. Task Breakdown by Phase (maps to proposal's Milestones)

### Phase 1 — Prompt Suite Design (~1.5 wks)
1. Draft 40–60 prompts across the 4 categories (aim ~10–15 each for balance)
2. For each prompt, write a self-checking reference testbench (assert-based, not just `$display`)
3. Validate every testbench against a hand-written *known-correct* reference implementation — this must pass 100% before moving on
4. Tag each prompt with a difficulty label (trivial/moderate/complex) for later stratified analysis
5. Freeze the prompt manifest (`prompt_manifest.yaml`) — no changes after benchmark execution starts, to keep the comparison fair

### Phase 2 — Correctness Harness (~1 wk)
1. Build `lint.py` (syntax/style pass, catches obvious garbage before wasting sim time)
2. Build `sim_runner.py`: compile + simulate against paired testbench in both Icarus and Verilator
3. Define failure taxonomy: syntax error / simulation mismatch / timeout / non-synthesizable construct / simulator disagreement (Icarus passes, Verilator fails, or vice versa — track this separately, it's a useful caveat)
4. Unit test the harness itself against a small set of intentionally broken RTL (off-by-one bit width, wrong sensitivity list, etc.) to confirm it actually catches what it claims to catch

### Phase 3 — On-Prem Serving Setup (~3–4 days)
1. Finalize fp16 baseline config (model, batch size, max concurrency)
2. Finalize INT8 config via PagedKV-Fusion, same model
3. Confirm both configs answer the same prompt with roughly consistent (not necessarily identical) output — sanity check before running the full suite

### Phase 4 — Cloud API Integration (~3–4 days)
1. Write thin client wrappers per provider with consistent timing instrumentation (client-side TTFT proxy, since Prometheus isn't available)
2. Match concurrency/rate-limit behavior as closely as cloud limits allow; document any forced deviation
3. Confirm cost accounting per call (track token usage returned by each API)

### Phase 5 — Benchmark Execution (~1 wk)
1. Run smoke test: 2–3 prompts × all 4 configs, confirm pipeline runs end-to-end and produces clean JSON
2. Execute full run matrix: 40–60 prompts × 4 configs × 5 repeated trials = 800–1200 total generations
3. Run within as tight a time window as feasible (proposal risk: cloud pricing/rate-limit drift)
4. Store all raw results untouched in `results/raw/`

### Phase 6 — Correctness Analysis (~1 wk)
1. Run every generated snippet through the eval harness; record pass/fail + failure category
2. Build paired comparison: same prompt, fp16 vs INT8 (and vs cloud) — did quantization flip a pass to a fail?
3. Compute confidence intervals on pass rates; run paired significance test (paired t-test or Wilcoxon) on the fp16-vs-INT8 comparison specifically
4. Categorize and manually inspect every paired-comparison failure — pull the actual diff, note *why* it failed

### Phase 7 — Validation Report & Dashboard (~1.5 wks)
1. Auto-generate `VALIDATION_REPORT.md` from processed results (don't hand-copy numbers — script it, so it's regenerable)
2. Include: exact hardware/software config, full latency distributions (P50/P95/P99), cost tables, correctness pass rates per config, paired-failure diffs, explicit sample-size and confidence-interval disclosures
3. Wire Grafana dashboard to show latency + cost + correctness overlay
4. Final pass: does every claim in the report trace to a script and a result file? Remove/soften anything that doesn't.

---

## 5. Immediate Next Actions (this week)

1. Confirm GPU and record exact specs (blocks everything else)
2. Pick the specific open-weight model (blocks Phases 1 sanity checks, 3, 4)
3. Draft first 10 prompts + testbenches in one category (e.g., peripherals) as a pilot — validates your prompt/testbench format before committing to all 40–60
4. Set up the repo skeleton above and get CI running on an empty/smoke-test harness

---

## 6. Open Decisions to Nail Down Early
- Exact open-weight model + size (fits fp16 in your VRAM budget?)
- Which 2 cloud providers, and same-model-family vs different-flagship framing
- Number of repeated trials per prompt (proposal suggests 5 — confirm this is enough given cost/time budget)
- Icarus vs Verilator disagreement handling — treat as a third failure category, don't silently pick one
