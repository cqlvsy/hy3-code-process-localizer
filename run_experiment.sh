#!/bin/bash
set -e
echo "=== EXPERIMENT START $(date) ==="
echo "--- MBPP+ (30 problems, with SBFL) ---"
hcp-eval run --dataset mbppplus --sample-size 30 --output-dir results/mbppplus 2>&1 | tail -25
echo "--- HumanEval+ (30 problems, with SBFL) ---"
hcp-eval run --dataset humanevalplus --sample-size 30 --output-dir results/humanevalplus 2>&1 | tail -25
echo "=== EXPERIMENT DONE $(date) ==="
