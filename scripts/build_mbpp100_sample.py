#!/usr/bin/env python3
"""Build a 100-problem MBPP+ sample file for the §4 expansion.

Strategy: PRESERVE the original 30-sample problems (so the §12.3 validation
subset's 13 task IDs remain resolvable) and append 70 more distinct problems
pulled from the full EvalPlus MBPP+ set (378 total).

Writes back to data/imported_mbppplus_sample.jsonl (the path the adapter and the
§12.3 regeneration script both read).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from hcp_eval.adapters.evalplus_adapter import EvalPlusAdapter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = DATA / "imported_mbppplus_sample.jsonl"
OUT = SRC  # overwrite in place


def main() -> None:
    # 1. Original 30 (kept first for stable ordering / validation-subset coverage)
    original: list[dict] = []
    if SRC.exists():
        for line in SRC.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                original.append(json.loads(line))
    orig_ids = {d["task_id"] for d in original}
    print(f"Original sample: {len(original)} problems ({len(orig_ids)} unique ids)")

    # 2. Full MBPP+ from official EvalPlus API
    adapter = EvalPlusAdapter(dataset_name="mbppplus")
    full = adapter._load_from_evalplus()
    print(f"Full MBPP+ available: {len(full)}")

    # 3. Pick 70 distinct problems not already in the original 30
    rng = random.Random(7)
    extra = [p for p in full if p.task_id not in orig_ids]
    print(f"Candidates outside original 30: {len(extra)}")
    rng.shuffle(extra)
    chosen = extra[:70]
    print(f"Appended {len(chosen)} new problems")

    # 4. Merge (original 30 first) and write
    merged = original + [p.model_dump() for p in chosen]
    OUT.write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in merged) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(merged)} problems -> {OUT}")


if __name__ == "__main__":
    main()
