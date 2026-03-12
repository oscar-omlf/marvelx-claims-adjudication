from __future__ import annotations

import os
from typing import Dict, List


ALLOWED_TEXT_EXTENSIONS = {".txt", ".md"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def list_claim_directories(dataset_dir: str) -> List[str]:
    dirs = [
        os.path.join(dataset_dir, name)
        for name in os.listdir(dataset_dir)
        if name.lower().startswith("claim ") and os.path.isdir(os.path.join(dataset_dir, name))
    ]
    return sorted(dirs, key=lambda p: int(os.path.basename(p).split()[1]))


def load_claim_folder(claim_dir: str) -> Dict[str, object]:
    files = []
    description = ""
    for name in sorted(os.listdir(claim_dir)):
        path = os.path.join(claim_dir, name)
        if not os.path.isfile(path):
            continue
        if name == "answer.json":
            continue
        ext = os.path.splitext(name)[1].lower()
        kind = "other"
        if ext in ALLOWED_TEXT_EXTENSIONS:
            kind = "text"
        elif ext in ALLOWED_IMAGE_EXTENSIONS:
            kind = "image"
        files.append({"filename": name, "path": path, "kind": kind})
        if name == "description.txt":
            with open(path, "r", encoding="utf-8") as f:
                description = f.read()
    return {
        "claim_id": os.path.basename(claim_dir).replace(" ", "_"),
        "claim_name": os.path.basename(claim_dir),
        "claim_dir": claim_dir,
        "description": description,
        "files": files,
    }
