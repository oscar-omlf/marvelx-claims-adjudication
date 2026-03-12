from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from ..schemas import ClaimAssessment, DocumentAssessment, DocumentRecord, Signal
from ..extraction.parsers import best_datetime, parse_booking_record, extract_patient_and_doctor_lines
from ..extraction.normalization import canonicalize_concepts, normalize_text


MEDICAL_SUPPORT_PATTERNS = [
    r"hospitalization",
    r"admission",
    r"admitted",
    r"emergency",
    r"surgery",
    r"operation",
    r"diagnosed",
    r"diagnosis",
    r"rest(?:\s+for|\s+period|\s+and)?",
    r"strict bed rest",
    r"not to travel",
    r"travel advised against",
    r"unable to travel",
    r"unfit",
    r"incapable",
]
MEDICAL_CONTRADICTION_PATTERNS = [
    r"healthy",
    r"clinically healthy",
    r"perfect state of health",
    r"good condition",
    r"good clinical condition",
    r"buenas condiciones clinicas",
    r"perfecto estado de salud",
    r"fit to travel",
    r"fit for travel",
    r"fit for physical activity",
    r"apto para realizar actividad fisica",
    r"apto para actividad fisica",
    r"normal condition",
    r"sin alteraciones",
    r"clinicamente sana",
    r"clinicamente sano",
]
THEFT_PATTERNS = [r"theft", r"robbery", r"stolen", r"criminal incident", r"police"]
LEGAL_PATTERNS = [r"jury", r"summons", r"court", r"hearing"]
ACCIDENT_PATTERNS = [r"accident", r"collision", r"traffic", r"delay", r"missed"]


class PolicyEngine:
    def assess_claim(self, claim_id: str, description: str, documents: List[DocumentRecord]) -> ClaimAssessment:
        normalized_description = canonicalize_concepts(description)
        booking_docs = [d for d in documents if d.document_type == "booking"]
        medical_docs = [d for d in documents if d.document_type == "medical"]
        police_docs = [d for d in documents if d.document_type == "police"]
        legal_docs = [d for d in documents if d.document_type == "legal"]

        travel_facts = self._aggregate_travel_facts(booking_docs)
        incident_facts = self._extract_incident_facts(description, normalized_description)
        coverage_type = self._classify_coverage(normalized_description, medical_docs, police_docs, legal_docs)

        assessments: List[DocumentAssessment] = []
        support: List[Signal] = []
        contradiction: List[Signal] = []
        hard_invalidity: List[Signal] = []
        soft_uncertainty: List[Signal] = []
        warnings: List[str] = []

        booking_ok, booking_signal, booking_warnings = self._verify_booking(booking_docs, travel_facts)
        warnings.extend(booking_warnings)
        if booking_signal:
            if booking_ok:
                support.append(booking_signal)
            else:
                hard_invalidity.append(booking_signal)

        for doc in medical_docs:
            da = self._assess_medical_document(doc, travel_facts, normalized_description)
            assessments.append(da)
            support.extend(da.support_signals)
            contradiction.extend(da.contradiction_signals)
            hard_invalidity.extend(da.hard_invalidity_signals)
            soft_uncertainty.extend(da.soft_uncertainty_signals)

        for doc in police_docs:
            da = self._assess_generic_official_document(doc, "theft")
            assessments.append(da)
            support.extend(da.support_signals)
            hard_invalidity.extend(da.hard_invalidity_signals)

        for doc in legal_docs:
            da = self._assess_generic_official_document(doc, "legal")
            assessments.append(da)
            support.extend(da.support_signals)
            hard_invalidity.extend(da.hard_invalidity_signals)

        support.extend(self._description_support_signals(normalized_description, coverage_type))
        contradiction.extend(self._description_contradictions(normalized_description, coverage_type))
        hard_invalidity.extend(self._policy_invalidities(coverage_type, normalized_description, medical_docs, police_docs, legal_docs, booking_ok))
        soft_uncertainty.extend(self._description_uncertainties(normalized_description, travel_facts, medical_docs))

        decision, explanation, confidence = self._route_decision(
            coverage_type=coverage_type,
            support=support,
            contradiction=contradiction,
            hard_invalidity=hard_invalidity,
            soft_uncertainty=soft_uncertainty,
        )

        payout, currency = self._estimate_payout(coverage_type, decision, travel_facts)

        policy_summary = {
            "booking_proof_present": booking_ok,
            "medical_doc_count": len(medical_docs),
            "police_doc_count": len(police_docs),
            "legal_doc_count": len(legal_docs),
            "support_signal_count": len(support),
            "contradiction_signal_count": len(contradiction),
            "hard_invalidity_count": len(hard_invalidity),
            "soft_uncertainty_count": len(soft_uncertainty),
        }

        return ClaimAssessment(
            claim_id=claim_id,
            coverage_type=coverage_type,
            decision=decision,
            explanation=explanation,
            confidence=confidence,
            payout_estimate=payout,
            currency=currency,
            warnings=warnings,
            travel_facts=travel_facts,
            incident_facts=incident_facts,
            policy_summary=policy_summary,
            documents=documents,
            document_assessments=assessments,
            support_signals=support,
            contradiction_signals=contradiction,
            hard_invalidity_signals=hard_invalidity,
            soft_uncertainty_signals=soft_uncertainty,
        )

    def _aggregate_travel_facts(self, booking_docs: List[DocumentRecord]) -> Dict[str, Any]:
        aggregated: Dict[str, Any] = {}
        for doc in booking_docs:
            parsed = parse_booking_record(doc.raw_text)
            doc.extracted_fields.update(parsed)
            for k, v in parsed.items():
                if v is not None and k not in aggregated:
                    aggregated[k] = v
        return aggregated

    def _extract_incident_facts(self, description: str, norm_desc: str) -> Dict[str, Any]:
        return {
            "description_mentions_medical": any(re.search(p, norm_desc) for p in MEDICAL_SUPPORT_PATTERNS),
            "description_mentions_theft": any(re.search(p, norm_desc) for p in THEFT_PATTERNS),
            "description_mentions_legal": any(re.search(p, norm_desc) for p in LEGAL_PATTERNS),
            "description_mentions_accident": any(re.search(p, norm_desc) for p in ACCIDENT_PATTERNS),
            "description_mentions_healthy": any(re.search(p, norm_desc) for p in MEDICAL_CONTRADICTION_PATTERNS),
        }

    def _classify_coverage(self, norm_desc: str, medical_docs: List[DocumentRecord], police_docs: List[DocumentRecord], legal_docs: List[DocumentRecord]) -> str:
        if "appointment" in norm_desc and "travel" in norm_desc and not medical_docs:
            return "not_covered"
        if any(re.search(p, norm_desc) for p in LEGAL_PATTERNS) or legal_docs:
            return "legal_cancellation"
        if any(re.search(p, norm_desc) for p in THEFT_PATTERNS) or police_docs:
            if "belongings" in norm_desc or "luggage" in norm_desc or "hotel" in norm_desc:
                return "personal_effects"
            return "theft_cancellation"
        if medical_docs or any(re.search(p, norm_desc) for p in MEDICAL_SUPPORT_PATTERNS + MEDICAL_CONTRADICTION_PATTERNS):
            return "medical_cancellation"
        if any(re.search(p, norm_desc) for p in ACCIDENT_PATTERNS):
            return "missed_departure"
        return "not_covered"

    def _verify_booking(self, booking_docs: List[DocumentRecord], travel_facts: Dict[str, Any]) -> Tuple[bool, Signal | None, List[str]]:
        warnings: List[str] = []
        if not booking_docs:
            return False, Signal(code="missing_booking_proof", message="proof of booking is missing", severity="high", decisive=True), warnings
        if not any(travel_facts.get(k) for k in ["booking_ref", "flight", "train", "hotel", "event"]):
            warnings.append("Booking proof exists but structured travel fields were sparse.")
        return True, Signal(code="booking_proof_present", message="booking proof is present", severity="low"), warnings

    def _assess_medical_document(self, doc: DocumentRecord, travel_facts: Dict[str, Any], normalized_description: str) -> DocumentAssessment:
        text = canonicalize_concepts(doc.raw_text)
        facts = extract_patient_and_doctor_lines(doc.raw_text)
        facts.update(doc.extracted_fields)
        assessment = DocumentAssessment(
            document_id=doc.document_id,
            document_type=doc.document_type,
            trust_tier="authoritative_image" if doc.modality == "image" else "structured_text",
            extracted_facts=facts,
        )

        if doc.modality == "text":
            assessment.hard_invalidity_signals.append(
                Signal(
                    code="text_only_medical_doc",
                    message="medical support is provided only as plain text rather than an official medical image or scanned record",
                    source_document=doc.filename,
                    decisive=True,
                    severity="high",
                )
            )

        booking_name = normalize_text(str(travel_facts.get("name") or ""))
        description_norm = normalize_text(normalized_description)
        full_name_text = normalize_text(" ".join(facts.get("names", [])) + " " + doc.raw_text)
        has_name_match = bool(booking_name and self._names_compatible(booking_name, full_name_text))
        has_doctor_line = bool(facts.get("doctor_lines")) or bool(re.search(r"\bdr\.?\b", text)) or any(token in text for token in ["doctor", "docteur", "medico", "physician"])
        has_institution = any(token in text for token in ["hospital", "clinic", "clinique", "clinica", "medical center", "hopital", "ospedale", "hospital universitario"])
        has_signature_cue = any(token in text for token in ["signature", "firma", "cachet", "seal", "timbro"])

        if any(re.search(p, text) for p in MEDICAL_CONTRADICTION_PATTERNS):
            assessment.contradiction_signals.append(
                Signal(
                    code="medical_doc_states_healthy",
                    message="the medical document indicates the traveler is healthy or fit rather than unable to travel",
                    source_document=doc.filename,
                    decisive=True,
                    severity="high",
                )
            )

        if any(re.search(p, text) for p in MEDICAL_SUPPORT_PATTERNS) or has_institution or doc.filename.lower().count("medical"):
            assessment.support_signals.append(
                Signal(
                    code="medical_support_present",
                    message="the medical document contains hospitalization, diagnosis, emergency, surgery, rest, or unfitness cues",
                    source_document=doc.filename,
                    severity="medium",
                )
            )

        if "not to travel" in text or "travel advised against" in text or "unable to travel" in text:
            assessment.support_signals.append(
                Signal(
                    code="explicit_no_travel_advice",
                    message="the medical document explicitly advises against travel",
                    source_document=doc.filename,
                    severity="high",
                )
            )

        departure_dt = best_datetime(travel_facts.get("departure") or travel_facts.get("check_in") or travel_facts.get("event date"))
        current_dt = best_datetime(travel_facts.get("current_date"))
        if departure_dt and current_dt and (departure_dt.date() - current_dt.date()).days > 1:
            if any(token in text for token in ["hospitalization", "admission", "admitted", "hospitalizada", "hospitalized", "hospital", "hospitalizado"]):
                assessment.soft_uncertainty_signals.append(
                    Signal(
                        code="future_departure_unclear_recovery",
                        message="the flight is still in the future, so it is not clear if the person will still be unable to travel",
                        source_document=doc.filename,
                        severity="medium",
                    )
                )

        if not has_name_match:
            if any(term in description_norm for term in ["daughter", "son", "mom", "mother", "partner", "wife", "husband", "child"]):
                assessment.soft_uncertainty_signals.append(
                    Signal(
                        code="patient_identity_differs_but_family_related",
                        message="the medical document appears to belong to a related traveler rather than the claimant",
                        source_document=doc.filename,
                        severity="low",
                    )
                )
            elif doc.ocr_quality == "high" and (("certificat" in text or "certificado" in text or "constancia" in text) or "incapable" in text or "apto" in text or "unfit" in text) and not assessment.contradiction_signals:
                assessment.hard_invalidity_signals.append(
                    Signal(
                        code="identity_missing_or_redacted",
                        message="the patient identity is missing, redacted, or does not clearly match the booking",
                        source_document=doc.filename,
                        decisive=True,
                        severity="high",
                    )
                )

        if ("dada de alta" in text or "discharge" in text or "fecha de egreso" in text) and not re.search(r"(dada de alta|discharge|fecha de egreso)[:\s\-]*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})", text):
            assessment.hard_invalidity_signals.append(
                Signal(
                    code="discharge_without_clear_date",
                    message="the document mentions discharge but does not provide a coherent discharge date",
                    source_document=doc.filename,
                    decisive=True,
                    severity="high",
                )
            )

        if "[hospital_name]" in text or "[city]" in text:
            assessment.hard_invalidity_signals.append(
                Signal(
                    code="placeholder_content_present",
                    message="the supporting medical material appears templated or altered because placeholder text is still present",
                    source_document=doc.filename,
                    decisive=True,
                    severity="high",
                )
            )

        if departure_dt:
            for raw_line in doc.raw_text.splitlines():
                low = raw_line.lower()
                if "fait" in low:
                    dt = best_datetime(raw_line)
                    if dt is not None and dt.date() < departure_dt.date() and (departure_dt.date() - dt.date()).days > 7:
                        assessment.soft_uncertainty_signals.append(
                            Signal(
                                code="suspicious_document_dating",
                                message="the document has a suspicious date pattern that does not line up cleanly with the travel incident",
                                source_document=doc.filename,
                                severity="medium",
                            )
                        )
                        break
            non_birth_years = []
            for raw_line in doc.raw_text.splitlines():
                low = raw_line.lower()
                if any(tok in low for tok in ["dob", "nee", "nac", "nata", "born"]):
                    continue
                for y in re.findall(r"\b(19\d{2}|20\d{2})\b", raw_line):
                    non_birth_years.append(int(y))
            if non_birth_years and any(y > departure_dt.year for y in non_birth_years):
                assessment.soft_uncertainty_signals.append(
                    Signal(
                        code="late_document_year",
                        message="the document contains a later year stamp that makes its dating somewhat suspicious",
                        source_document=doc.filename,
                        severity="medium",
                    )
                )

        if not has_signature_cue and not has_doctor_line and not has_institution and not assessment.contradiction_signals and doc.ocr_quality == "high":
            assessment.soft_uncertainty_signals.append(
                Signal(
                    code="medical_authenticity_unresolved",
                    message="the medical document lacks a clear signature or attending-doctor attribution",
                    source_document=doc.filename,
                    severity="medium",
                )
            )
        if ("coordinador" in text or "coordinator" in text or "admisiones" in text or "admissions" in text) and not has_doctor_line and not has_signature_cue:
            assessment.soft_uncertainty_signals.append(
                Signal(
                    code="non_physician_hospital_note",
                    message="the document looks like an administrative hospital note rather than a signed physician certificate",
                    source_document=doc.filename,
                    severity="medium",
                )
            )

        if doc.ocr_quality == "poor" and not assessment.contradiction_signals and not assessment.hard_invalidity_signals:
            if "medical" in doc.filename.lower():
                assessment.support_signals.append(
                    Signal(
                        code="medical_image_attached",
                        message="an image that appears to be medical evidence was attached",
                        source_document=doc.filename,
                        severity="low",
                    )
                )
            else:
                assessment.soft_uncertainty_signals.append(
                    Signal(
                        code="image_attached_instead_of_clear_certificate",
                        message="only a low-readability picture was attached instead of a clear medical certificate",
                        source_document=doc.filename,
                        severity="medium",
                    )
                )

        if assessment.support_signals and not assessment.contradiction_signals and not assessment.hard_invalidity_signals:
            assessment.summary = "medical document provides support"
        elif assessment.contradiction_signals:
            assessment.summary = "medical document contradicts the claimed inability to travel"
        elif assessment.hard_invalidity_signals:
            assessment.summary = "medical document is not sufficiently reliable"
        else:
            assessment.summary = "medical document remains inconclusive"
        return assessment

    def _assess_generic_official_document(self, doc: DocumentRecord, mode: str) -> DocumentAssessment:
        text = canonicalize_concepts(doc.raw_text)
        assessment = DocumentAssessment(
            document_id=doc.document_id,
            document_type=doc.document_type,
            trust_tier="authoritative_image" if doc.modality == "image" else "structured_text",
        )
        if mode == "theft":
            if any(re.search(p, text) for p in THEFT_PATTERNS):
                assessment.support_signals.append(Signal(code="theft_document_present", message="police or theft documentation is present", source_document=doc.filename))
            else:
                assessment.hard_invalidity_signals.append(Signal(code="weak_theft_document", message="the theft documentation does not clearly describe a criminal incident", source_document=doc.filename, decisive=True, severity="high"))
        elif mode == "legal":
            if any(re.search(p, text) for p in LEGAL_PATTERNS):
                assessment.support_signals.append(Signal(code="legal_document_present", message="legal summons-style documentation is present", source_document=doc.filename))
            else:
                assessment.hard_invalidity_signals.append(Signal(code="weak_legal_document", message="the legal documentation is not clearly a summons or mandatory appearance", source_document=doc.filename, decisive=True, severity="high"))
        return assessment

    def _description_support_signals(self, norm_desc: str, coverage_type: str) -> List[Signal]:
        signals: List[Signal] = []
        if coverage_type == "medical_cancellation" and any(re.search(p, norm_desc) for p in MEDICAL_SUPPORT_PATTERNS):
            signals.append(Signal(code="narrative_medical_reason", message="the claimant narrative describes a medical reason for cancellation", source_document="description.txt", severity="low"))
        if coverage_type == "missed_departure" and any(re.search(p, norm_desc) for p in ACCIDENT_PATTERNS):
            signals.append(Signal(code="narrative_delay_reason", message="the claimant narrative describes a delay or missed departure reason", source_document="description.txt", severity="low"))
        return signals

    def _description_contradictions(self, norm_desc: str, coverage_type: str) -> List[Signal]:
        signals: List[Signal] = []
        if coverage_type == "medical_cancellation" and any(re.search(p, norm_desc) for p in MEDICAL_CONTRADICTION_PATTERNS):
            signals.append(Signal(code="narrative_states_healthy", message="the narrative itself says the person was healthy or fit", source_document="description.txt", decisive=True, severity="high"))
        return signals

    def _policy_invalidities(self, coverage_type: str, norm_desc: str, medical_docs: List[DocumentRecord], police_docs: List[DocumentRecord], legal_docs: List[DocumentRecord], booking_ok: bool) -> List[Signal]:
        signals: List[Signal] = []
        if coverage_type == "not_covered":
            signals.append(Signal(code="not_covered_reason", message="the claim reason does not match a covered policy category", decisive=True, severity="high"))
            return signals
        if not booking_ok:
            signals.append(Signal(code="missing_booking_proof", message="proof of booking is missing", decisive=True, severity="high"))
        if coverage_type == "medical_cancellation" and not medical_docs:
            signals.append(Signal(code="missing_medical_report", message="a medical claim requires a supporting medical report", decisive=True, severity="high"))
        if "appointment" in norm_desc and "clinic" in norm_desc and not medical_docs:
            signals.append(Signal(code="not_covered_personal_appointment", message="missing a personal medical appointment because of travel is not a covered insured event", decisive=True, severity="high"))
        if coverage_type in {"theft_cancellation", "personal_effects"} and not police_docs:
            signals.append(Signal(code="missing_police_report", message="theft-related claims require a police report or equivalent acknowledgement", decisive=True, severity="high"))
        if coverage_type == "legal_cancellation" and not legal_docs:
            signals.append(Signal(code="missing_legal_proof", message="legal-obligation claims require a summons or mandatory legal document", decisive=True, severity="high"))
        return signals

    def _description_uncertainties(self, norm_desc: str, travel_facts: Dict[str, Any], medical_docs: List[DocumentRecord]) -> List[Signal]:
        signals: List[Signal] = []
        if "following day" in norm_desc or "the following day" in norm_desc:
            signals.append(Signal(code="medical_visit_after_trip", message="the medical consultation occurred after the travel date according to the narrative", source_document="description.txt", severity="medium"))
        if medical_docs and "hope" in norm_desc and "recover" in norm_desc:
            signals.append(Signal(code="future_recovery_unclear", message="the narrative suggests recovery timing was uncertain close to departure", source_document="description.txt", severity="low"))
        departure_dt = best_datetime(travel_facts.get("departure") or travel_facts.get("check_in") or travel_facts.get("event date"))
        current_dt = best_datetime(travel_facts.get("current_date"))
        if medical_docs and departure_dt and current_dt and (departure_dt.date() - current_dt.date()).days > 7:
            if "still admitted" in norm_desc or "still hospitalized" in norm_desc or "still hospital" in norm_desc:
                signals.append(Signal(code="future_hospitalization_uncertain", message="the flight is still in the future, so it is not clear if the person will still be hospitalized or otherwise unable to fly", source_document="description.txt", severity="medium"))
        return signals

    def _route_decision(self, coverage_type: str, support: List[Signal], contradiction: List[Signal], hard_invalidity: List[Signal], soft_uncertainty: List[Signal]) -> Tuple[str, str, float]:
        if any(s.code == "not_covered_reason" for s in hard_invalidity):
            return "DENY", self._best_message(hard_invalidity, fallback="the claim reason is not covered by the policy"), 0.96
        if contradiction:
            return "DENY", self._best_message(contradiction, fallback="official evidence contradicts the claimed covered reason"), 0.95
        if hard_invalidity:
            return "DENY", self._best_message(hard_invalidity, fallback="required supporting documentation is missing or invalid"), 0.92
        if support and not soft_uncertainty:
            return "APPROVE", self._best_message(support, fallback="the claim is supported by covered documentation"), 0.88
        if support and soft_uncertainty:
            heavy_uncertainty = [s for s in soft_uncertainty if s.severity in {"medium", "high"}]
            if not heavy_uncertainty:
                return "APPROVE", self._best_message(support, fallback="the claim is supported by covered documentation"), 0.79
            return "UNCERTAIN", self._best_message(soft_uncertainty, fallback="the claim has some support but the documentation remains unresolved"), 0.62
        if coverage_type == "missed_departure":
            return "DENY", "the missed departure reason is not sufficiently documented as a covered incident", 0.8
        return "DENY", "the claim lacks sufficient valid support for approval", 0.84

    def _estimate_payout(self, coverage_type: str, decision: str, travel_facts: Dict[str, Any]) -> Tuple[float | None, str | None]:
        amount = travel_facts.get("price")
        currency = travel_facts.get("currency")
        if decision != "APPROVE":
            return None, currency
        if coverage_type == "personal_effects":
            return 100.0, "EUR"
        if coverage_type == "missed_departure" and amount is not None:
            return round(0.5 * float(amount), 2), currency
        if amount is not None:
            return round(float(amount), 2), currency
        return None, currency

    def _best_message(self, signals: List[Signal], fallback: str) -> str:
        if not signals:
            return fallback
        decisive = [s for s in signals if s.decisive]
        source = decisive[0] if decisive else signals[0]
        return source.message.rstrip(".")

    def _names_compatible(self, booking_name: str, medical_name: str) -> bool:
        booking_tokens = {t for t in re.findall(r"[a-z]+", booking_name) if len(t) > 2}
        medical_tokens = {t for t in re.findall(r"[a-z]+", medical_name) if len(t) > 2}
        if not booking_tokens or not medical_tokens:
            return True
        overlap = booking_tokens & medical_tokens
        return len(overlap) >= max(1, min(2, len(booking_tokens) // 2))
