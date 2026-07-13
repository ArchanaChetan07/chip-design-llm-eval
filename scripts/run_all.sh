#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Creating / activating venv"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -U pip
python -m pip install -q -r requirements.txt

echo "==> Tools"
set +o pipefail
iverilog -V 2>&1 | head -1
verilator --version | head -1
set -o pipefail
python -c "import flask,requests,yaml,pytest,anthropic; print('python deps ok')"

echo "==> 1. Validate testbenches"
python scripts/validate_testbenches.py

echo "==> 2. Unit tests"
python -m pytest tests/ -v

# Host port 8000 is often occupied; use 18000/18001 for local mock run.
FP16_PORT=18000
INT8_PORT=18001

echo "==> 3. Start mock servers on ${FP16_PORT}/${INT8_PORT}"
pkill -f "mock_vllm_server.py" 2>/dev/null || true
sleep 1
python serving/mock_vllm_server.py --port "$FP16_PORT" --profile fp16 > /tmp/mock_fp16.log 2>&1 &
FP16_PID=$!
python serving/mock_vllm_server.py --port "$INT8_PORT" --profile int8 > /tmp/mock_int8.log 2>&1 &
INT8_PID=$!
trap 'kill $FP16_PID $INT8_PID 2>/dev/null || true' EXIT

CONFIGS="$(mktemp)"
cat > "$CONFIGS" <<EOF
[
  {"name": "fp16", "kind": "onprem", "base_url": "http://127.0.0.1:${FP16_PORT}"},
  {"name": "int8", "kind": "onprem", "base_url": "http://127.0.0.1:${INT8_PORT}"}
]
EOF

for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${FP16_PORT}/health" >/dev/null \
     && curl -sf "http://127.0.0.1:${INT8_PORT}/health" >/dev/null; then
    echo "mock servers ready"
    break
  fi
  sleep 0.5
done
if ! curl -sf "http://127.0.0.1:${FP16_PORT}/health" >/dev/null; then
  echo "ERROR: mock fp16 server failed to start" >&2
  cat /tmp/mock_fp16.log >&2 || true
  exit 1
fi

echo "==> 4. Request runner"
mkdir -p results/raw results/processed
python harness/request_runner.py \
  --manifest prompts/prompt_manifest.yaml \
  --configs "$CONFIGS" \
  --trials 3 --output-dir results/raw
rm -f "$CONFIGS"

set +o pipefail
LATEST=$(ls -t results/raw/*.json | head -1)
set -o pipefail
if [[ -z "${LATEST}" ]]; then
  echo "ERROR: no raw results found" >&2
  exit 1
fi
echo "Using results: $LATEST"

echo "==> 5. Paired comparison"
python eval/paired_comparison.py \
  --raw-results "$LATEST" \
  --manifest prompts/prompt_manifest.yaml \
  --output results/processed/summary.json \
  --compare fp16 int8

echo "==> 6. Generate report"
python scripts/generate_report.py --summary results/processed/summary.json

echo "==> DONE"
echo "Summary: results/processed/summary.json"
echo "Report:  VALIDATION_REPORT.md"
