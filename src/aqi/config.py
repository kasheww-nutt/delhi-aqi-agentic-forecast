from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path = "configs/delhi.yaml") -> dict:
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    text = path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    cfg["_path"] = str(path)
    cfg["_sha"] = hashlib.sha256(text.encode()).hexdigest()[:12]
    return cfg


def resolve(rel: str) -> Path:
    """Paths in the config are relative to the repository root."""
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p
