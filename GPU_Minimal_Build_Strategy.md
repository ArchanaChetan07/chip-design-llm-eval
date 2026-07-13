# Build Order Strategy — Minimize GPU Rental Time

Goal: everything that can be built/tested without a GPU gets built first, locally, and fully validated. The GPU rental window is reserved *only* for the actual benchmark execution runs (Phase 5) plus a short smoke test. Target: rent GPU for maybe 1–2 sessions total, not the whole project.

---

## What needs a GPU vs. what doesn't

| Needs GPU | Does NOT need GPU |
|---|---|
| Actual vLLM fp16 inference | Prompt suite + testbench authoring |
| Actual PagedKV-Fusion INT8 inference | Correctness harness (Icarus/Verilator run on CPU) |
| Real TTFT/TPOT/E2EL numbers | Cloud API client code (calls real APIs, no local GPU needed) |
| Confirming PagedKV-Fusion kernel loads | Metrics collector, cost model, paired-comparison logic |
| Final full run matrix | Grafana/Prometheus dashboard wiring (can feed fake data first) |
| | CI/CD, repo scaffolding |
| | Report generation scripts |
| | Testbench validation against hand-written known-good RTL |

Everything in the right column is ~80% of total engineering effort. Build and fully debug all of it first.

---

## Revised Build Order

### Stage 0 — Repo + CI (no GPU)
- Scaffold repo structure, get CI green on empty tests

### Stage 1 — Prompt Suite + Testbenches (no GPU)
- Write all 40–60 prompts
- Write every reference testbench
- Validate every testbench against **hand-written correct RTL** (you write the RTL yourself, not an LLM) — this alone proves the eval harness works, zero GPU needed
- This is the most labor-intensive phase and fully GPU-independent — do it now

### Stage 2 — Correctness Harness (no GPU)
- `lint.py`, `sim_runner.py` (Icarus + Verilator both run fine on CPU)
- Failure taxonomy + unit tests using intentionally-broken RTL you write by hand
- Fully done and tested before any model ever runs

### Stage 3 — Cloud API Integration (no GPU, minimal $)
- Build client wrappers for 2 cloud providers
- Test against a handful of cheap real calls (few cents) — this is real API usage but zero GPU rental
- Get client-side timing instrumentation working and validated

### Stage 4 — Harness + Mock Serving Layer (no GPU) ★ key step
- Build `request_runner.py`, `metrics_collector.py`, `cost_model.py`
- Build a **mock vLLM server**: a tiny local Flask/FastAPI stub that mimics vLLM's `/v1/completions` and `/metrics` Prometheus endpoint format, returning canned RTL (or randomly perturbed/broken RTL) with artificial latency
- Run the *entire* pipeline end-to-end against: mock on-prem server + real cloud APIs
- This validates 100% of orchestration logic, metrics scraping format, cost computation, and results storage — the only unvalidated piece left is "does real vLLM + real PagedKV-Fusion behave like the mock," which is a much smaller, bounded risk

### Stage 5 — Dashboard Wiring (no GPU)
- Point Grafana at Prometheus fed by the mock server + real cloud client metrics
- Confirm dashboard panels render correctly with fake-but-realistic data
- Fix all dashboard/query issues now, not during rented GPU time

### Stage 6 — Paired Comparison + Report Generation (no GPU)
- Build `paired_comparison.py` and the `VALIDATION_REPORT.md` auto-generator against mock results
- Confirm the full report pipeline runs end-to-end and produces sensible output
- By this point: every piece of code has run at least once successfully, except real GPU inference

### Stage 7 — GPU Rental Session #1: Smoke Test (short, cheap)
- Rent RTX 3090/4090/A5000 for a short session (aim: under an hour)
- Stand up real vLLM fp16 + PagedKV-Fusion INT8 with your chosen model
- Run 2–3 prompts through the *real* pipeline built in Stages 0–6
- Confirm: metrics scrape correctly, PagedKV-Fusion loads and roughly matches prior throughput claims, generated RTL flows through the eval harness correctly
- Fix anything that breaks — this is exactly the point of a cheap smoke test before committing to the full run
- Terminate the rental as soon as smoke test passes and fixes are confirmed

### Stage 8 — GPU Rental Session #2: Full Benchmark Execution
- With everything pre-validated, this session is pure execution: run the full matrix (40–60 prompts × configs × 5 trials)
- Estimate duration in advance from the smoke test's per-generation timing, so you can budget the rental window precisely instead of renting "until it's done"
- Store all raw results; terminate rental immediately after confirming results are saved
- All analysis, report generation, and dashboard work happens *after*, GPU-free, using Stage 6's already-built pipeline

---

## Why this ordering minimizes cost
- The mock server in Stage 4 is the critical unlock — it turns "debug the whole pipeline while paying for a GPU" into "debug for free, then execute for pay"
- Testbench/harness bugs (the most likely source of wasted iteration) get caught and fixed on CPU
- Cloud API costs are separate from GPU rental and much cheaper to iterate against
- The two GPU sessions have sharply different, bounded purposes (smoke test vs. execution), so you're not paying for open-ended debugging time on rented hardware

---

## Model choice note (RTX 3090/4090/A5000 — 24GB)
With 24GB instead of the T1000's 8GB, you have real headroom:
- A 7B coding model fits comfortably at fp16 (~14GB) with room for KV cache
- Leaves room to also test a larger model if you want a secondary data point, without changing your core plan
- Still worth explicitly disclosing which specific GPU you rent (3090 vs 4090 vs A5000 have different memory bandwidth/compute — matters for TTFT/throughput comparability across runs, so rent the *same* GPU model for both smoke test and full run)

---

## Immediate next step
Start Stage 0 + Stage 1 now — repo scaffold and the first pilot batch of ~10 prompts/testbenches in one category. Want me to scaffold the repo (Stage 0) and write the mock vLLM server (Stage 4) now, so you have working code to build against?
