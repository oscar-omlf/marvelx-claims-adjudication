from __future__ import annotations

import re
import unicodedata
from typing import Dict


def strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    text = strip_accents(text or "")
    text = text.lower()
    text = text.replace("€", " eur ").replace("$", " usd ")
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


MULTILINGUAL_CONCEPTS: Dict[str, str] = {
    "hospitalizacion": "hospitalization",
    "hospitalizada": "hospitalization",
    "hospitalizado": "hospitalization",
    "hospitalisation": "hospitalization",
    "hospitalized": "hospitalization",
    "admisiones": "admission",
    "admission": "admission",
    "urgencias": "emergency",
    "emergency": "emergency",
    "emergencia": "emergency",
    "operation chirurgicale": "surgery",
    "chirurgicale": "surgery",
    "cirugia": "surgery",
    "surgery": "surgery",
    "reposo": "rest",
    "repose": "rest",
    "rest": "rest",
    "incapable": "unfit",
    "incapacite": "unfit",
    "incapacidad": "unfit",
    "unfit": "unfit",
    "no apto": "unfit",
    "not travel": "not_travel",
    "bed rest": "rest",
    "strict bed rest": "rest",
    "healthy": "healthy",
    "sana": "healthy",
    "sano": "healthy",
    "clinically healthy": "healthy",
    "clinicamente sana": "healthy",
    "clinicamente sano": "healthy",
    "perfecto estado de salud": "healthy",
    "fit to travel": "fit",
    "fit for travel": "fit",
    "apto": "fit",
    "fit": "fit",
    "jury": "jury",
    "court": "court",
    "summons": "summons",
    "police": "police",
    "theft": "theft",
    "robbery": "theft",
    "stolen": "theft",
    "accident": "accident",
    "collision": "accident",
    "delay": "delay",
}


def canonicalize_concepts(text: str) -> str:
    normalized = normalize_text(text)
    for src, dest in sorted(MULTILINGUAL_CONCEPTS.items(), key=lambda kv: -len(kv[0])):
        normalized = normalized.replace(src, dest)
    return normalized
