"""
harness/cost_model.py

Computes $/module and $/1K tokens for each serving configuration, given
either published cloud pricing or measured on-prem GPU-hour cost.

Pricing is NOT hardcoded here -- it lives in a config file that gets
snapshotted at benchmark time (see scripts/snapshot_pricing.py), so every
number in the final report traces back to a dated, committed pricing source.
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CostBreakdown:
    config_name: str
    dollars_per_module: float
    dollars_per_1k_prompt_tokens: float
    dollars_per_1k_completion_tokens: float
    basis: str  # human-readable note on how this was computed


def load_pricing_config(path: str) -> dict:
    return json.loads(Path(path).read_text())


def cost_for_cloud_call(pricing: dict, provider: str, prompt_tokens: int,
                         completion_tokens: int) -> float:
    """pricing[provider] = {'prompt_per_1k': float, 'completion_per_1k': float}"""
    rates = pricing[provider]
    return (prompt_tokens / 1000.0) * rates["prompt_per_1k"] + \
           (completion_tokens / 1000.0) * rates["completion_per_1k"]


def cost_for_onprem_call(pricing: dict, config_name: str, wall_seconds: float) -> float:
    """pricing['onprem'][config_name] = {'gpu_hour_rate': float}
    Cost is purely time-based for on-prem (you're paying for the rental
    window regardless of tokens), which is itself a useful point of
    contrast against cloud's per-token pricing in the report."""
    rate = pricing["onprem"][config_name]["gpu_hour_rate"]
    return (wall_seconds / 3600.0) * rate


def summarize(config_name: str, is_cloud: bool, pricing: dict,
              total_modules: int, total_prompt_tokens: int,
              total_completion_tokens: int, total_wall_seconds: float) -> CostBreakdown:
    if is_cloud:
        total_cost = cost_for_cloud_call(
            pricing, config_name, total_prompt_tokens, total_completion_tokens
        )
        basis = f"cloud per-token pricing for '{config_name}' (see pricing_snapshot.json)"
    else:
        total_cost = cost_for_onprem_call(pricing, config_name, total_wall_seconds)
        basis = f"on-prem GPU-hour rate for '{config_name}', wall-clock {total_wall_seconds:.1f}s"

    return CostBreakdown(
        config_name=config_name,
        dollars_per_module=total_cost / max(total_modules, 1),
        dollars_per_1k_prompt_tokens=(total_cost / max(total_prompt_tokens, 1)) * 1000
                                      if total_prompt_tokens else 0.0,
        dollars_per_1k_completion_tokens=(total_cost / max(total_completion_tokens, 1)) * 1000
                                          if total_completion_tokens else 0.0,
        basis=basis,
    )
