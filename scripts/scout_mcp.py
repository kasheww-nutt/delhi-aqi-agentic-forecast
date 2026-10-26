"""MCP server "aqi-scout": pollution-source tools any MCP-capable CLI (Claude Code, Codex, Gemini, agy) can call.

    python scripts/scout_mcp.py            # stdio transport; started by the CLI, not by hand
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from aqi import scout_tools as T  # noqa: E402

server = MCPServer("aqi-scout", instructions=(
    "Tools for explaining air pollution at Delhi monitoring stations: crop fires (NASA FIRMS), "
    "mapped sources near a place (OpenStreetMap) and the station's latest AQI readings."))


def _safe(fn, *args):
    try:
        return json.dumps(fn(*args), ensure_ascii=False)
    except Exception as e:  # tools report problems as data so the model can carry on
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


@server.tool()
def fires(start_date: str = "", days: int = 1, region: str = "punjab_haryana") -> str:
    """Satellite fire detections (crop/stubble burning) from NASA FIRMS.
    start_date: YYYY-MM-DD (empty = the most recent days). days: 1-10.
    region: 'punjab_haryana' (upwind farm fires) or 'delhi_ncr'."""
    return _safe(T.fires, start_date or None, days, region)


@server.tool()
def nearby_sources(place: str, radius_km: float = 2.0) -> str:
    """Mapped pollution sources within radius_km (0.5-5) of a Delhi place or station name:
    construction sites, industrial areas, landfills, power plants and major roads (OpenStreetMap)."""
    return _safe(T.nearby_sources, place, radius_km)


@server.tool()
def station_snapshot(station: str, days: int = 7) -> str:
    """The station's latest daily AQI, category and PM2.5 from the most recent pipeline run."""
    return _safe(T.station_snapshot, station, days)


if __name__ == "__main__":
    server.run("stdio")
