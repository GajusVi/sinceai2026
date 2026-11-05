#!/bin/bash
# Pings several Aitta (LUMI) models in parallel, 120 s limit each; prints which ones answer and how fast.
cd "$(dirname "$0")" || exit 1
models=(Qwen/Qwen3.6-35B-A3B google/gemma-4-26B-A4B-it meta-llama/Llama-3.3-70B-Instruct openai/gpt-oss-120b LumiOpen/Llama-Poro-2-70B-Instruct)
for m in "${models[@]}"; do
  ( start=$(date +%s)
    out=$(LLM_PROVIDER=aitta LLM_MODEL=$m LLM_TIMEOUT_S=120 LLM_MAX_RETRIES=0 .venv/bin/python -m backend.llm 2>&1 | tail -1)
    echo "$(( $(date +%s) - start ))s  $m  ->  ${out: -80}" ) &
done
echo "testing ${#models[@]} models in parallel, up to 2 minutes..."
wait
