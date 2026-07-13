"""
harness/request_runner.py

Orchestrates the benchmark run matrix: for each prompt x serving-config x
trial, sends the prompt, records the generated RTL + timing, and writes a
raw JSON result. Works identically whether the on-prem endpoint is the mock
server (serving/mock_vllm_server.py) or a real vLLM instance -- same HTTP
contract, same result schema. This is the piece that gets fully exercised
and debugged now, so the later GPU rental session is pure execution.
"""
import argparse
import json
import time
import uuid
import sys
import yaml
import requests
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class ServingConfig:
    name: str
    kind: str          # "onprem" | "cloud"
    base_url: str       # e.g. http://127.0.0.1:8000 for onprem/mock
    api_key_env: Optional[str] = None  # for cloud configs


@dataclass
class TrialResult:
    run_id: str
    prompt_id: str
    config_name: str
    trial_index: int
    generated_text: str
    ttft_s: float
    e2el_s: float
    prompt_tokens: int
    completion_tokens: int
    timestamp: float
    error: Optional[str] = None


def load_prompt_manifest(path: str) -> list:
    manifest = yaml.safe_load(Path(path).read_text())
    return manifest["prompts"]


def call_onprem(config: ServingConfig, prompt_text: str, inject_bug: bool = False) -> dict:
    """Calls a vLLM-compatible /v1/completions endpoint (mock or real)."""
    payload = {"prompt": prompt_text, "max_tokens": 512, "temperature": 0.2}
    if inject_bug:
        payload["_mock_inject_bug"] = True  # no-op against real vLLM, used only for mock testing
    t0 = time.time()
    resp = requests.post(f"{config.base_url}/v1/completions", json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    wall = time.time() - t0

    # Prefer server-reported timing if present (mock provides it); otherwise
    # fall back to client-side wall clock as a TTFT/E2EL proxy -- this is
    # exactly the fallback path used for cloud APIs that don't expose /metrics.
    timing = data.get("_mock_timing", {})
    return {
        "text": data["choices"][0]["text"],
        "prompt_tokens": data["usage"]["prompt_tokens"],
        "completion_tokens": data["usage"]["completion_tokens"],
        "ttft_s": timing.get("ttft_s", wall * 0.3),   # crude proxy fallback
        "e2el_s": timing.get("e2el_s", wall),
    }


def call_cloud(config: ServingConfig, prompt_text: str) -> dict:
    """
    Dispatches to a real provider client module based on config.name.
    Each client returns the same dict shape as call_onprem():
      {text, prompt_tokens, completion_tokens, ttft_s, e2el_s}

    To add a new provider: write serving/cloud_clients/<provider>_client.py
    exposing a call(prompt_text, model, api_key_env) -> dict function
    matching that contract, then register it in CLOUD_CLIENT_REGISTRY below.
    """
    if config.name not in CLOUD_CLIENT_REGISTRY:
        raise NotImplementedError(
            f"No cloud client registered for config '{config.name}'. "
            f"Registered: {list(CLOUD_CLIENT_REGISTRY.keys())}. "
            f"Add one in serving/cloud_clients/ and register it in "
            f"harness/request_runner.py's CLOUD_CLIENT_REGISTRY."
        )
    client_fn, model = CLOUD_CLIENT_REGISTRY[config.name]
    return client_fn(prompt_text, model=model, api_key_env=config.api_key_env)


def _load_cloud_client_registry():
    """Lazily imports cloud client modules so this file doesn't hard-fail
    at import time if a provider's SDK isn't installed and that provider
    isn't being used in this run."""
    registry = {}
    try:
        from serving.cloud_clients import anthropic_client
        registry["cloud_anthropic"] = (anthropic_client.call, "claude-sonnet-4-6")
    except ImportError:
        pass
    # Add additional providers here as they're wired in, e.g.:
    # try:
    #     from serving.cloud_clients import provider_b_client
    #     registry["cloud_provider_b"] = (provider_b_client.call, "some-model")
    # except ImportError:
    #     pass
    return registry


CLOUD_CLIENT_REGISTRY = _load_cloud_client_registry()


def run_matrix(prompts: list, configs: list, n_trials: int, output_dir: str,
               mock_inject_bug_configs: Optional[list] = None):
    """
    mock_inject_bug_configs: list of config names for which the mock server
    should be told to inject a correctness bug (used ONLY to test that the
    downstream eval/paired-comparison pipeline correctly detects a
    quantization-induced regression, before any real GPU is involved).
    """
    mock_inject_bug_configs = mock_inject_bug_configs or []
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())[:8]

    results = []
    for prompt in prompts:
        for config in configs:
            for trial in range(n_trials):
                inject_bug = config["name"] in mock_inject_bug_configs
                try:
                    if config["kind"] == "onprem":
                        cfg = ServingConfig(**config)
                        out = call_onprem(cfg, prompt["prompt"], inject_bug=inject_bug)
                        error = None
                    else:
                        cfg = ServingConfig(**config)
                        out = call_cloud(cfg, prompt["prompt"])
                        error = None
                except NotImplementedError as e:
                    out = {"text": "", "prompt_tokens": 0, "completion_tokens": 0,
                           "ttft_s": 0.0, "e2el_s": 0.0}
                    error = str(e)

                result = TrialResult(
                    run_id=run_id,
                    prompt_id=prompt["id"],
                    config_name=config["name"],
                    trial_index=trial,
                    generated_text=out["text"],
                    ttft_s=out["ttft_s"],
                    e2el_s=out["e2el_s"],
                    prompt_tokens=out["prompt_tokens"],
                    completion_tokens=out["completion_tokens"],
                    timestamp=time.time(),
                    error=error,
                )
                results.append(result)

    out_file = output_path / f"raw_results_{run_id}.json"
    out_file.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Wrote {len(results)} trial results to {out_file}")
    return out_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="prompts/prompt_manifest.yaml")
    parser.add_argument("--configs", required=True,
                         help="JSON file listing serving configs, see serving/configs.example.json")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--output-dir", default="results/raw")
    parser.add_argument("--inject-bug-configs", nargs="*", default=[],
                         help="Config names to inject a mock correctness bug into (mock testing only)")
    args = parser.parse_args()

    prompts = load_prompt_manifest(args.manifest)
    configs = json.loads(Path(args.configs).read_text())
    run_matrix(prompts, configs, args.trials, args.output_dir, args.inject_bug_configs)
