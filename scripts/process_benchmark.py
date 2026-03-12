from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from claims_pipeline.loaders.claim_loader import list_claim_directories
from claims_pipeline.orchestrator import ClaimProcessor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=None)
    args = parser.parse_args()

    processor = ClaimProcessor()
    claim_dirs = list_claim_directories(args.dataset)
    end = args.end if args.end is not None else len(claim_dirs)
    claim_dirs = [c for c in claim_dirs if args.start <= int(os.path.basename(c).split()[1]) <= end]
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for idx, claim_dir in enumerate(claim_dirs, start=1):
            print(f"Processing {idx}/{len(claim_dirs)}: {os.path.basename(claim_dir)}", flush=True)
            assessment = processor.process_claim_dir(claim_dir)
            f.write(json.dumps(assessment.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
    print(f"Wrote {len(claim_dirs)} predictions to {args.output}", flush=True)


if __name__ == "__main__":
    main()
