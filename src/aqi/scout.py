"""Source scout: an LLM agent that explains what is polluting a station *now*.

It runs a coding-agent CLI (Claude Code) with three MCP tools from scripts/scout_mcp.py (NASA FIRMS
fires, OpenStreetMap sources, the station's latest readings) plus web search for live news such as
construction, GRAP orders or landfill fires. Output is a short brief with every claim sourced.

For explanation and live use only: it never feeds training data, because web pages and maps
describe the present and would leak hindsight into past dates.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from .config import ROOT, load_config
from .ledger import Ledger
from .llm import LLM

SERVER = "aqi-scout"
MCP = {
    "servers": {SERVER: {"command": sys.executable, "args": [str(ROOT / "scripts" / "scout_mcp.py")]}},
    "tools": [f"mcp__{SERVER}__fires", f"mcp__{SERVER}__nearby_sources", f"mcp__{SERVER}__station_snapshot"],
}

SYSTEM = """You are the source-scout agent of a Delhi air-quality forecasting project. Explain what is
likely driving pollution at one monitoring station right now. Use the tools: station_snapshot for its
latest AQI, fires for crop burning in Punjab-Haryana over the last few days, nearby_sources for mapped
construction, industry, landfills and big roads within 2 km, and web search for this week's news (active
construction or demolition, GRAP stage and bans, landfill or waste fires, traffic, festivals).
If a tool returns an error, say so in one line and continue with the others. Never invent a source.
Write in plain English for a city official: short Markdown with a one-sentence answer first, then
bullets under 'Recent air quality', 'Likely drivers' (each with its evidence), 'What would help', and
'Sources' (tool names, and links for anything from the web). Under 250 words."""


def scout(station: str, run_id: str | None = None) -> dict:
    cfg = load_config()["llm"]
    ledger = Ledger(run_id or f"scout-{datetime.now():%Y%m%d-%H%M%S}")
    ledger.log("source_scout", "start", f"scouting {station}")
    llm = LLM({**cfg, "cli": [c for c in cfg.get("cli", ["claude"]) if c == "claude"] or ["claude"]},
              ledger, agent="source_scout", mcp=MCP, timeout=420)
    brief = llm.ask(SYSTEM, f"Station: {station}. Today is {datetime.now():%d %B %Y}.", web=True)
    ok = isinstance(brief, str) and brief.strip()
    ledger.log("source_scout", "info" if ok else "error",
               f"brief for {station}" if ok else f"no brief: {llm.disabled_reason}",
               station=station, brief=brief if ok else None)
    ledger.log("source_scout", "done" if ok else "error")
    return {"run": ledger.run_id, "station": station, "brief": brief if ok else None,
            "error": None if ok else llm.disabled_reason}


if __name__ == "__main__":  # python -m aqi.scout [--run-id ID] Anand Vihar
    args = sys.argv[1:]
    run_id = args.pop(args.index("--run-id") + 1) if "--run-id" in args else None
    args = [a for a in args if a != "--run-id"]
    out = scout(" ".join(args) or "Anand Vihar", run_id)
    print(out["brief"] or f"Scout failed: {out['error']}")
    print(f"\n(ledger: runs/{out['run']}/ledger.jsonl)")
