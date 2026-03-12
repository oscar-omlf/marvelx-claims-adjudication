from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Signal:
    code: str
    message: str
    source_document: Optional[str] = None
    snippet: Optional[str] = None
    severity: str = "medium"
    decisive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentRecord:
    document_id: str
    filename: str
    path: str
    modality: str
    raw_text: str
    normalized_text: str
    ocr_quality: str = "n/a"
    document_type: str = "unknown"
    authoritative_roles: List[str] = field(default_factory=list)
    extracted_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentAssessment:
    document_id: str
    document_type: str
    trust_tier: str
    extracted_facts: Dict[str, Any] = field(default_factory=dict)
    support_signals: List[Signal] = field(default_factory=list)
    contradiction_signals: List[Signal] = field(default_factory=list)
    hard_invalidity_signals: List[Signal] = field(default_factory=list)
    soft_uncertainty_signals: List[Signal] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in [
            "support_signals",
            "contradiction_signals",
            "hard_invalidity_signals",
            "soft_uncertainty_signals",
        ]:
            data[key] = [s.to_dict() for s in getattr(self, key)]
        return data


@dataclass
class ClaimAssessment:
    claim_id: str
    coverage_type: str
    decision: str
    explanation: str
    confidence: float
    payout_estimate: Optional[float]
    currency: Optional[str]
    warnings: List[str]
    travel_facts: Dict[str, Any]
    incident_facts: Dict[str, Any]
    policy_summary: Dict[str, Any]
    documents: List[DocumentRecord]
    document_assessments: List[DocumentAssessment]
    support_signals: List[Signal]
    contradiction_signals: List[Signal]
    hard_invalidity_signals: List[Signal]
    soft_uncertainty_signals: List[Signal]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "coverage_type": self.coverage_type,
            "decision": self.decision,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "payout_estimate": self.payout_estimate,
            "currency": self.currency,
            "warnings": self.warnings,
            "travel_facts": self.travel_facts,
            "incident_facts": self.incident_facts,
            "policy_summary": self.policy_summary,
            "documents": [d.to_dict() for d in self.documents],
            "document_assessments": [d.to_dict() for d in self.document_assessments],
            "support_signals": [s.to_dict() for s in self.support_signals],
            "contradiction_signals": [s.to_dict() for s in self.contradiction_signals],
            "hard_invalidity_signals": [s.to_dict() for s in self.hard_invalidity_signals],
            "soft_uncertainty_signals": [s.to_dict() for s in self.soft_uncertainty_signals],
        }
