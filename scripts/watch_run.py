"""Follow a pipeline run live in the terminal: one line per agent event, as it happens.

    python scripts/watch_run.py cams-full
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = {"start": "▶", "info": "·", "done": "✓", "halt": "■", "halted": "■", "error": "✗", "llm": "$"}


def main(run_id: str) -> None:
    path = ROOT / "runs" / run_id / "ledger.jsonl"
    print(f"Waiting for run '{run_id}' to start…", flush=True)
    while not path.exists():
        time.sleep(3)
    seen = 0
    while True:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[seen:]:
            e = json.loads(line)
            t = datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
            extra = f" ({e['seconds']}s)" if e.get("seconds") is not None and e["status"] == "done" else ""
            text = e.get("command") if e["status"] == "llm" else e.get("summary", "")
            print(f"{t} {MARK.get(e['status'], ' ')} {e['node']:<15} {text or ''}{extra}", flush=True)
            if e["node"] == "pipeline" and e["status"] in ("done", "halted"):
                print("\nRun finished.", flush=True)
                return
        seen = len(lines)
        time.sleep(2)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cams-full")
