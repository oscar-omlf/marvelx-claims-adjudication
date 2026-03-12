from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from claims_pipeline.orchestrator import ClaimProcessor


def run() -> None:
    dataset = os.environ.get("CLAIMS_DATASET")
    if dataset and os.path.isdir(os.path.join(dataset, "claim 8")):
        assessment = ClaimProcessor().process_claim_dir(os.path.join(dataset, "claim 8"))
        assert assessment.decision in {"APPROVE", "DENY", "UNCERTAIN"}
        assert assessment.coverage_type
    print("smoke tests passed")


if __name__ == "__main__":
    run()
