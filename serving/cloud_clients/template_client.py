"""
serving/cloud_clients/template_client.py

Template for a real cloud provider client. Copy this file per provider
(e.g. provider_a_client.py) and fill in the marked sections. Keeping the
return contract identical to call_onprem()'s output in
harness/request_runner.py is what lets the rest of the pipeline (metrics,
cost model, paired comparison) work unchanged across on-prem and cloud.

DO NOT invent a provider's API shape from memory -- check their current
docs when you wire this in for real; API contracts (param names, response
schema, streaming vs non-streaming) do change.
"""
import os
import time


def call(prompt_text: str, model: str, api_key_env: str) -> dict:
    """
    Returns dict matching call_onprem()'s contract:
      {
        "text": str,
        "prompt_tokens": int,
        "completion_tokens": int,
        "ttft_s": float,   # if the provider doesn't expose TTFT, use a
                            # client-side proxy: time from request sent to
                            # first byte received (requires streaming mode)
        "e2el_s": float,   # client-side wall clock, request to full response
      }
    """
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key in env var {api_key_env}")

    t_start = time.time()

    # --- TODO: replace with real provider SDK/HTTP call ---
    # Example shape (DO NOT rely on this without checking current docs):
    #
    #   import anthropic
    #   client = anthropic.Anthropic(api_key=api_key)
    #   with client.messages.stream(
    #       model=model,
    #       max_tokens=512,
    #       messages=[{"role": "user", "content": prompt_text}],
    #   ) as stream:
    #       first_token_time = None
    #       chunks = []
    #       for text in stream.text_stream:
    #           if first_token_time is None:
    #               first_token_time = time.time()
    #           chunks.append(text)
    #       final = stream.get_final_message()
    #   ttft_s = first_token_time - t_start
    #   e2el_s = time.time() - t_start
    #   return {
    #       "text": "".join(chunks),
    #       "prompt_tokens": final.usage.input_tokens,
    #       "completion_tokens": final.usage.output_tokens,
    #       "ttft_s": ttft_s,
    #       "e2el_s": e2el_s,
    #   }
    raise NotImplementedError("Fill in real provider call above before Stage 3/7 execution.")
