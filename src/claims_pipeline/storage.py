from __future__ import annotations

from typing import Dict, List, Optional

from .schemas import ClaimAssessment


class ClaimStore:
    def __init__(self) -> None:
        self._items: Dict[str, ClaimAssessment] = {}

    def upsert(self, assessment: ClaimAssessment) -> None:
        self._items[assessment.claim_id] = assessment

    def get(self, claim_id: str) -> Optional[ClaimAssessment]:
        return self._items.get(claim_id)

    def list(self) -> List[ClaimAssessment]:
        return [self._items[k] for k in sorted(self._items)]
