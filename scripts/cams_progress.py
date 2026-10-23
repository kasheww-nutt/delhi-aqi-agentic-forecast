"""Live progress bar for scripts/fetch_cams.py (reads the files on disk; safe to start and stop anytime).

    python scripts/cams_progress.py --start 2018-01 --end 2025-12
"""
from __future__ import annotations

import argparse
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "cams"
LOG = ROOT / "runs" / "cams_download.log"


def last_resume() -> float:
    """Time the download was last (re)started, from the '--- resumed' markers in its log."""
    if not LOG.exists():
        return 0.0
    hits = re.findall(r"--- resumed (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", LOG.read_text(encoding="utf-8", errors="ignore"))
    return datetime.strptime(hits[-1], "%Y-%m-%d %H:%M:%S").timestamp() if hits else 0.0


def fmt(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


def snapshot(months: list[pd.Period]) -> tuple[list[pd.Period], list[float]]:
    done, stamps = [], []
    for p in months:
        f = OUT / f"cams_{p.year}{p.month:02d}.zip"
        if f.exists():
            done.append(p)
            stamps.append(f.stat().st_mtime)
    return done, sorted(stamps)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01")
    ap.add_argument("--end", default="2025-12")
    ap.add_argument("--every", type=float, default=5, help="refresh interval in seconds")
    args = ap.parse_args()
    months = list(pd.period_range(args.start, args.end, freq="M"))

    while True:
        done, stamps = snapshot(months)
        n, total = len(done), len(months)
        pending = [p for p in months if p not in set(done)]
        recent = [b - a for a, b in zip(stamps, stamps[1:]) if 0 < b - a < 3600][-8:]  # last few gaps
        pace = sum(recent) / len(recent) if recent else None
        eta = pace * len(pending) if pace and pending else None
        since = time.time() - max(stamps[-1] if stamps else 0, last_resume())
        size = sum(f.stat().st_size for f in OUT.glob("cams_*.zip")) / 1e6

        if pending:
            tail = f" {pending[0]} waiting {fmt(since)}"
            tail += f" | {pace / 60:.1f} min/mo | ETA {fmt(eta)} (~{datetime.now() + timedelta(seconds=eta):%H:%M})" if eta else ""
        else:
            tail = " done" + (" · daily file ✓" if (OUT / "cams_daily_delhi.csv").exists() else " · building daily file")
        head = f" {n}/{total} {100 * n / total:3.0f}% {size:.1f}MB |"
        cols = shutil.get_terminal_size((100, 20)).columns - 1
        width = max(10, min(30, cols - len(head) - len(tail) - 2))
        filled = int(width * n / total)
        line = f"[{'█' * filled}{'░' * (width - filled)}]{head}{tail}"[:cols]
        print("\r" + line.ljust(cols), end="", flush=True)
        if not pending and (OUT / "cams_daily_delhi.csv").exists():
            print()
            break
        time.sleep(args.every)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
