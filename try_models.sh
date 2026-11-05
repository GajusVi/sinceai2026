#!/bin/bash
# Tries several Gemini models with a 25 s limit each and reports which ones answer.
cd "$(dirname "$0")" || exit 1
for m in gemini-3.5-flash-lite gemini-flash-lite-latest gemini-3.1-flash-lite gemini-2.5-flash-lite gemini-3.5-flash; do
  start=$(date +%s)
  out=$(LLM_PROVIDER=gemini LLM_MODEL=$m LLM_TIMEOUT_S=25 LLM_MAX_RETRIES=0 .venv/bin/python -m backend.llm 2>&1 | tail -1)
  echo "$(( $(date +%s) - start ))s  $m  ->  ${out: -90}"
done
