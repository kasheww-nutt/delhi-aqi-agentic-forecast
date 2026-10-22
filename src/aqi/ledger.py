"""Experiment ledger: an append-only record of every node run, decision and artifact.

The frontend reads only this file, so whatever the ledger shows is exactly what happened.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from .config import ROOT


class Ledger:
    def __init__(self, run_id: str | None = None, runs_dir: Path = ROOT / "runs"):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = runs_dir / self.run_id
        (self.dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (self.dir / "locked").mkdir(exist_ok=True)
        self.path = self.dir / "ledger.jsonl"

    def log(self, node: str, status: str, summary: str = "", **data) -> None:
        event = {"ts": time.time(), "node": node, "status": status, "summary": summary, **data}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def artifact(self, name: str) -> Path:
        return self.dir / "artifacts" / name

    def events(self) -> list[dict]:
        return read_events(self.path)


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
