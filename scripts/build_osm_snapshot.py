"""Save the OpenStreetMap pollution-source lookup for every station, for days when the public servers are busy.

The scout's nearby_sources tool tries the live servers first and falls back to this snapshot (marked with its
date). Mapped features change slowly, so a snapshot stays useful for months. Safe to stop and rerun: stations
already saved are skipped, and busy servers are retried.

    python scripts/build_osm_snapshot.py            # all stations in the newest pipeline run, 2 km
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from aqi import scout_tools as T  # noqa: E402

RADIUS_KM = 2.0


def stations() -> list[str]:
    runs = sorted((p for p in (T.ROOT / "runs").glob("*") if (p / "daily.parquet").exists()),
                  key=lambda p: p.stat().st_mtime)
    names = pd.read_parquet(runs[-1] / "daily.parquet", columns=["station"])["station"].astype(str).unique()
    # "301_Anand_Vihar_Delhi_DPCC" -> "Anand Vihar" (the same plain names the console's station list uses)
    return sorted({" ".join(n.split("_")[1:-2]) for n in names})


def overpass_up() -> bool:
    """A tiny query: is any public Overpass server answering right now?"""
    for url in T.OVERPASS:
        try:
            r = T.requests.post(url, data={"data": "[out:json][timeout:5];node(1);out;"}, headers=T.UA, timeout=10)
            if r.ok and r.text.lstrip().startswith("{"):
                return True
        except T.requests.RequestException:
            continue
    return False


def main(max_rounds: int = 60, pause_s: int = 60) -> None:
    snap = json.loads(T.SNAPSHOT.read_text(encoding="utf-8")) if T.SNAPSHOT.exists() else {"places": {}}
    todo = [s for s in stations() if T._slug(s) not in snap["places"]]
    for rnd in range(max_rounds):
        if not overpass_up():
            print(f"round {rnd + 1}: map servers busy, waiting {pause_s}s", flush=True)
            time.sleep(pause_s)
            continue
        for place in list(todo):
            try:
                snap["places"][T._slug(place)] = T._nearby_live(place, RADIUS_KM)
                todo.remove(place)
                print(f"saved {place}", flush=True)
            except Exception as e:  # busy servers or a place Nominatim cannot find: try again next round
                print(f"retry later: {place} ({type(e).__name__}: {str(e)[:80]})", flush=True)
            time.sleep(2)  # be polite to the public servers
        snap.update(taken=str(date.today()), radius_km=RADIUS_KM)
        T.SNAPSHOT.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
        if not todo:
            break
        print(f"round {rnd + 1}: {len(todo)} left, waiting {pause_s}s", flush=True)
        time.sleep(pause_s)
    print(f"done: {len(snap['places'])} stations saved, {len(todo)} missing: {todo}")


if __name__ == "__main__":
    main()
