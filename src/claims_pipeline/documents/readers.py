from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageOps
import pytesseract


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_CACHE_DIR = Path(os.environ.get("CLAIMS_OCR_CACHE_DIR", Path(__file__).resolve().parents[3] / ".ocr_cache"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _clean_ocr_text(text: str) -> str:
    text = text.replace("\x0c", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _cache_key(path: str) -> str:
    stat = os.stat(path)
    payload = f"{os.path.abspath(path)}::{stat.st_mtime_ns}::{stat.st_size}".encode()
    return hashlib.sha1(payload).hexdigest()


def _load_cache(path: str) -> Tuple[str, str] | None:
    cache_path = _CACHE_DIR / f"{_cache_key(path)}.json"
    if not cache_path.exists():
        return None
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    return data.get("text", ""), data.get("quality", "poor")


def _save_cache(path: str, text: str, quality: str) -> None:
    cache_path = _CACHE_DIR / f"{_cache_key(path)}.json"
    cache_path.write_text(json.dumps({"text": text, "quality": quality}, ensure_ascii=False), encoding="utf-8")


def ocr_image(path: str) -> Tuple[str, str]:
    cached = _load_cache(path)
    if cached is not None:
        return cached

    image = Image.open(path)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)

    max_dim = max(gray.size)
    if max_dim > 1200:
        ratio = 1200 / max_dim
        gray = gray.resize((max(1, int(gray.width * ratio)), max(1, int(gray.height * ratio))))
    elif max_dim < 700:
        gray = gray.resize((gray.width * 2, gray.height * 2))

    texts = []
    variants = [(gray, "--psm 6")]
    for variant, config in variants:
        try:
            text = _clean_ocr_text(pytesseract.image_to_string(variant, config=config, timeout=6))
        except Exception:
            text = ""
        texts.append(text)

    best = max(texts, key=lambda t: (len(t), sum(c.isalpha() for c in t))) if texts else ""
    quality = "high" if len(best) > 250 else "partial" if len(best) > 80 else "poor"
    _save_cache(path, best, quality)
    return best, quality


def read_file(path: str) -> Tuple[str, str, str]:
    ext = os.path.splitext(path)[1].lower()
    if ext in _IMAGE_EXTENSIONS:
        text, quality = ocr_image(path)
        return text, "image", quality
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), "text", "n/a"
