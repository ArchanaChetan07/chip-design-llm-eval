# Chip-design LLM eval — reproducible Icarus + Verilator toolchain
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Dual simulators (apt) — the barrier this image exists to remove
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iverilog \
        verilator \
        make \
        g++ \
        python3 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && iverilog -V | head -n 1 \
    && verilator --version | head -n 1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: prove the dual-simulator harness works (no LLM / no host EDA tools)
CMD ["sh", "-c", "python scripts/validate_testbenches.py && pytest -q"]
