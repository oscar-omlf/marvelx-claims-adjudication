from __future__ import annotations

from typing import List


def classify_document(filename: str, normalized_text: str) -> str:
    fname = filename.lower()
    text = normalized_text
    if filename == "description.txt":
        return "description"
    if any(k in fname for k in ["boarding pass", "booking confirmation", "ticket data", "flight data", "train data", "supporting", "internal flight", "internal train", "internal ticket"]):
        return "booking"
    if any(k in fname for k in ["medical", "hospital", "dental", "admission"]) or any(
        k in text for k in [
            "hospital",
            "medical center",
            "certificat",
            "certificate",
            "diagnosis",
            "diagnostico",
            "doctor",
            "physician",
            "clinica",
            "hospitalization",
        ]
    ):
        return "medical"
    if any(k in text for k in ["police", "complaint", "robbery", "theft", "stolen"]):
        return "police"
    if any(k in text for k in ["jury", "summons", "court", "tribunal"]):
        return "legal"
    return "unknown"


def authoritative_roles_for_type(document_type: str) -> List[str]:
    mapping = {
        "booking": ["booking_proof"],
        "medical": ["medical_proof"],
        "police": ["police_proof"],
        "legal": ["legal_proof"],
        "description": ["narrative"],
    }
    return mapping.get(document_type, ["supporting"])
