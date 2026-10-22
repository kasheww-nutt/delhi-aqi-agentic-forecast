"""Run the full agentic pipeline.

    python scripts/run_pipeline.py                      # default config
    python scripts/run_pipeline.py --leaky-demo         # proves the Leakage Guard stops a leaky run
    AQI_REPLAY_FROM=<run_id> python scripts/run_pipeline.py   # replay cached LLM decisions
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aqi.config import load_config  # noqa: E402
from aqi.graph import run  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/delhi.yaml")
    ap.add_argument("--run-id")
    ap.add_argument("--leaky-demo", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.leaky_demo:
        cfg["features"]["leaky_demo"] = True
    if args.no_llm:
        cfg["llm"]["enabled"] = False
    final, ledger = run(cfg, args.run_id)
    print(f"run {ledger.run_id}: {'HALTED — ' + final['halted'] if final.get('halted') else 'done'}")
    print(f"ledger: {ledger.path}")


if __name__ == "__main__":
    main()
