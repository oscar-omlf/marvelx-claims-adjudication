from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser as dateparser


KEY_ALIASES = {
    "name": ["name", "nombre", "patient name"],
    "claimant": ["claimant"],
    "booking_ref": ["booking ref", "booking reference", "reference de reserva", "booking platform confirmation number", "confirmation number"],
    "price": ["price", "ticket price", "ticket cost", "precio", "payment date", "cost"],
    "operator": ["operator", "airline", "operador"],
    "flight": ["flight", "flight number"],
    "train": ["train", "tren"],
    "hotel": ["hotel", "hotel name"],
    "event": ["event"],
    "departure": ["departure", "salida", "event date", "check-in", "date"],
    "from": ["from", "origin", "desde"],
    "to": ["to", "destination", "hacia"],
    "booked_on": ["booked on", "date of booking", "registered on", "reservado el", "payment date"],
    "current_date": ["current date is", "current date"],
    "check_in": ["check-in", "check in", "check-in date"],
    "check_out": ["check-out", "check out", "check-out date"],
}


def parse_key_value_lines(text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("*")
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        k = re.sub(r"\*", "", key).strip().lower()
        v = value.strip()
        fields[k] = v
    return fields


def _get_alias_value(fields: Dict[str, str], canonical: str) -> Optional[str]:
    aliases = KEY_ALIASES.get(canonical, [])
    for alias in aliases:
        for key, value in fields.items():
            if key == alias or key.startswith(alias):
                return value
    return None


def parse_booking_record(text: str) -> Dict[str, Any]:
    fields = parse_key_value_lines(text)
    parsed: Dict[str, Any] = {
        "raw_fields": fields,
        "name": _get_alias_value(fields, "name"),
        "claimant": _get_alias_value(fields, "claimant"),
        "booking_ref": _get_alias_value(fields, "booking_ref"),
        "operator": _get_alias_value(fields, "operator"),
        "flight": _get_alias_value(fields, "flight"),
        "train": _get_alias_value(fields, "train"),
        "hotel": _get_alias_value(fields, "hotel"),
        "event": _get_alias_value(fields, "event"),
        "departure": _get_alias_value(fields, "departure"),
        "from": _get_alias_value(fields, "from"),
        "to": _get_alias_value(fields, "to"),
        "booked_on": _get_alias_value(fields, "booked_on"),
        "current_date": _get_alias_value(fields, "current_date"),
        "check_in": _get_alias_value(fields, "check_in"),
        "check_out": _get_alias_value(fields, "check_out"),
    }
    price_text = _get_alias_value(fields, "price")
    amount, currency = parse_amount(price_text or "")
    parsed["price"] = amount
    parsed["currency"] = currency
    return parsed


def parse_amount(text: str) -> Tuple[Optional[float], Optional[str]]:
    if not text:
        return None, None
    currency = None
    norm = text.replace(",", "")
    if "eur" in norm.lower() or "€" in text:
        currency = "EUR"
    elif "usd" in norm.lower() or "$" in text:
        currency = "USD"
    match = re.search(r"(-?\d+(?:\.\d{1,2})?)", norm)
    if not match:
        return None, currency
    try:
        return float(match.group(1)), currency
    except ValueError:
        return None, currency


def parse_dates_from_text(text: str) -> List[datetime]:
    dates: List[datetime] = []
    patterns = re.findall(r"\b\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2})?", text)
    for p in patterns:
        try:
            dates.append(dateparser.parse(p, fuzzy=False))
        except Exception:
            pass
    return dates


def best_datetime(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return dateparser.parse(text, fuzzy=True, dayfirst=False)
    except Exception:
        return None


def extract_patient_and_doctor_lines(text: str) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    for line in text.splitlines():
        low = line.lower()
        if "patient name" in low or low.startswith("name:") or low.startswith("nombre:"):
            facts.setdefault("names", []).append(line.split(":", 1)[-1].strip())
        if "doctor" in low or low.startswith("dr") or "medecin" in low or "physician" in low:
            facts.setdefault("doctor_lines", []).append(line.strip())
        if "signature" in low or "firma" in low or "cachet" in low or "seal" in low:
            facts.setdefault("signature_lines", []).append(line.strip())
    return facts
