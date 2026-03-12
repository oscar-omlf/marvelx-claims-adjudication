from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class InlineDocument(BaseModel):
    filename: str
    content: str


class ClaimSubmission(BaseModel):
    claim_id: Optional[str] = None
    description: Optional[str] = None
    documents: List[InlineDocument] = Field(default_factory=list)
    claim_path: Optional[str] = None


class ClaimResponse(BaseModel):
    claim_id: str
    decision: str
    explanation: str
    confidence: float
    coverage_type: str
    payout_estimate: Optional[float] = None
    currency: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    extracted_facts: Dict[str, object] = Field(default_factory=dict)
    policy_assessment_summary: Dict[str, object] = Field(default_factory=dict)
