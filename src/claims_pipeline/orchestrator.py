from __future__ import annotations

from typing import List

from .documents.readers import read_file
from .extraction.classifiers import authoritative_roles_for_type, classify_document
from .extraction.normalization import canonicalize_concepts
from .loaders.claim_loader import load_claim_folder
from .policy.engine import PolicyEngine
from .schemas import DocumentRecord, ClaimAssessment


class ClaimProcessor:
    def __init__(self) -> None:
        self.policy_engine = PolicyEngine()

    def process_claim_dir(self, claim_dir: str) -> ClaimAssessment:
        payload = load_claim_folder(claim_dir)
        claim_id = payload["claim_id"]
        description = payload["description"]
        docs: List[DocumentRecord] = []
        for idx, f in enumerate(payload["files"]):
            raw_text, modality, ocr_quality = read_file(f["path"])
            normalized = canonicalize_concepts(raw_text)
            doc_type = classify_document(f["filename"], normalized)
            docs.append(
                DocumentRecord(
                    document_id=f"doc_{idx+1}",
                    filename=f["filename"],
                    path=f["path"],
                    modality=modality,
                    raw_text=raw_text,
                    normalized_text=normalized,
                    ocr_quality=ocr_quality,
                    document_type=doc_type,
                    authoritative_roles=authoritative_roles_for_type(doc_type),
                )
            )
        return self.policy_engine.assess_claim(claim_id=claim_id, description=description, documents=docs)

    def process_inline_claim(self, claim_id: str, description: str, inline_documents: List[dict]) -> ClaimAssessment:
        docs: List[DocumentRecord] = []
        for idx, item in enumerate(inline_documents):
            normalized = canonicalize_concepts(item["content"])
            doc_type = classify_document(item["filename"], normalized)
            docs.append(
                DocumentRecord(
                    document_id=f"doc_{idx+1}",
                    filename=item["filename"],
                    path="<inline>",
                    modality="text",
                    raw_text=item["content"],
                    normalized_text=normalized,
                    document_type=doc_type,
                    authoritative_roles=authoritative_roles_for_type(doc_type),
                )
            )
        return self.policy_engine.assess_claim(claim_id=claim_id, description=description, documents=docs)
