#!/bin/bash
# Supervisor: keeps the HumanEval+30 run going across external kills / crashes.
# The runner (run_humaneval30.py) writes results incrementally and resumes from
# eval_results.jsonl, so restarting is safe and continues from the last result.
set -u
cd /Users/cq/WorkBuddy/2026-09-07-12-24-04
PY=/Users/cq/.workbuddy/binaries/python/envs/default/bin/python
RUNNER=scripts/run_humaneval30.py
LOG=results/humaneval30_supervisor.log
JSONL=results/humanevalplus/eval_results.jsonl
TARGET=30
MAX_ATTEMPTS=20

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "[supervisor] attempt $i at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
  "$PY" "$RUNNER" >> "$LOG" 2>&1
  n=$(wc -l < "$JSONL" 2>/dev/null || echo 0)
  echo "[supervisor] after attempt $i: $n / $TARGET results" >> "$LOG"
  if [ "$n" -ge "$TARGET" ]; then
    echo "[supervisor] DONE: reached $TARGET results" >> "$LOG"
    break
  fi
  echo "[supervisor] not complete, restarting in 5s (attempt $((i+1)))" >> "$LOG"
  sleep 5
done
echo "[supervisor] supervisor exiting (final check below)" >> "$LOG"
n=$(wc -l < "$JSONL" 2>/dev/null || echo 0)
echo "[supervisor] final result count: $n / $TARGET" >> "$LOG"
