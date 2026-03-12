from __future__ import annotations

from ..schemas import ClaimAssessment


def to_api_payload(assessment: ClaimAssessment) -> dict:
    return {
        "claim_id": assessment.claim_id,
        "decision": assessment.decision,
        "explanation": assessment.explanation,
        "confidence": assessment.confidence,
        "coverage_type": assessment.coverage_type,
        "payout_estimate": assessment.payout_estimate,
        "currency": assessment.currency,
        "warnings": assessment.warnings,
        "extracted_facts": {
            "travel_facts": assessment.travel_facts,
            "incident_facts": assessment.incident_facts,
        },
        "policy_assessment_summary": assessment.policy_summary,
    }
