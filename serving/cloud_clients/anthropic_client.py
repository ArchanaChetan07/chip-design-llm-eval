"""
serving/cloud_clients/anthropic_client.py

Real cloud client for the Anthropic API. Returns the same dict shape as
harness/request_runner.py's call_onprem(), so it drops into the pipeline
with zero changes elsewhere (metrics, cost model, paired comparison).

TTFT is measured via streaming (time from request sent to first text
chunk received). E2EL is measured via wall clock from request sent to
stream completion. These are client-side proxies, not server-reported
values -- Anthropic's API does not expose a separate TTFT metric, so this
is the correct and only way to measure it for a cloud provider.
"""
import os
import time
import anthropic


def call(prompt_text: str, model: str = "claude-sonnet-4-6",
         api_key_env: str = "ANTHROPIC_API_KEY", max_tokens: int = 512) -> dict:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key in env var {api_key_env}")

    client = anthropic.Anthropic(api_key=api_key)

    t_start = time.time()
    first_token_time = None
    chunks = []

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt_text}],
    ) as stream:
        for text in stream.text_stream:
            if first_token_time is None:
                first_token_time = time.time()
            chunks.append(text)
        final_message = stream.get_final_message()

    e2el_s = time.time() - t_start
    ttft_s = (first_token_time - t_start) if first_token_time else e2el_s

    return {
        "text": "".join(chunks),
        "prompt_tokens": final_message.usage.input_tokens,
        "completion_tokens": final_message.usage.output_tokens,
        "ttft_s": ttft_s,
        "e2el_s": e2el_s,
    }


if __name__ == "__main__":
    # Smoke test: one real call, printed timing + a snippet of output.
    result = call(
        "Write a synthesizable SystemVerilog module named adder with a "
        "parameter WIDTH (default 8). Inputs a and b are WIDTH-bit unsigned. "
        "Output sum is WIDTH+1 bits and equals a+b exactly, including overflow. "
        "Return only the code, no explanation.",
        model="claude-sonnet-4-6",
    )
    print(f"TTFT: {result['ttft_s']:.3f}s")
    print(f"E2EL: {result['e2el_s']:.3f}s")
    print(f"Prompt tokens: {result['prompt_tokens']}, Completion tokens: {result['completion_tokens']}")
    print("--- Generated text (first 400 chars) ---")
    print(result["text"][:400])
