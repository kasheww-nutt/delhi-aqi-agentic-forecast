"""Pollution-source lookups used by the source-scout agent (exposed to LLM CLIs through MCP).

These answer "what around this station could be polluting it, today?". They are for explanation
and live use only, never training features: web pages and maps describe the present, so using
them for past dates would leak hindsight. NASA FIRMS counts are measured data and could become
features later.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from .config import ROOT

UA = {"User-Agent": "delhi-aqi-forecast/1.1"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
REGIONS = {  # west, south, east, north
    "punjab_haryana": (73.8, 29.5, 77.6, 32.6),
    "delhi_ncr": (76.8, 28.3, 77.6, 28.9),
}
DELHI_VIEWBOX = "76.8,28.9,77.6,28.3"
SNAPSHOT = Path(__file__).with_name("osm_snapshot.json")  # saved map answers per station, for busy days


def _firms_key() -> str:
    key = os.environ.get("FIRMS_MAP_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("FIRMS_MAP_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise RuntimeError("FIRMS_MAP_KEY is not set (put it in .env)")
    return key


def fires(start_date: str | None = None, days: int = 1, region: str = "punjab_haryana") -> dict:
    """Satellite fire detections (NASA FIRMS, VIIRS) in a region for up to 10 days from start_date."""
    days = max(1, min(int(days), 10))
    if region not in REGIONS:
        raise ValueError(f"unknown region '{region}'; use one of {sorted(REGIONS)}")
    w, s, e, n = REGIONS[region]
    start = date.fromisoformat(start_date) if start_date else date.today() - timedelta(days=days - 1)
    if start > date.today():
        raise ValueError(f"start_date {start} is in the future")
    recent = (date.today() - start).days < 60
    product = "VIIRS_SNPP_NRT" if recent else "VIIRS_SNPP_SP"   # near-real-time vs archive
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{_firms_key()}/{product}/{w},{s},{e},{n}/{days}/{start}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(r.text)) if r.text.strip() and "latitude" in r.text else pd.DataFrame()
    if df.empty:
        return {"region": region, "start": str(start), "days": days, "fires": 0, "source": "NASA FIRMS " + product}
    df["confidence"] = df["confidence"].astype(str)
    top = df.nlargest(5, "frp")[["latitude", "longitude", "acq_date", "frp"]]
    return {
        "region": region, "start": str(start), "days": days, "source": "NASA FIRMS " + product,
        "fires": int(len(df)),
        "high_confidence": int(df["confidence"].isin(["h", "high"]).sum()),
        "by_day": {str(k): int(v) for k, v in df.groupby("acq_date").size().items()},
        "total_fire_radiative_power_mw": round(float(df["frp"].sum()), 1),
        "strongest": top.round(3).to_dict(orient="records"),
    }


def geocode(place: str) -> dict:
    """Coordinates of a place in Delhi (OpenStreetMap Nominatim)."""
    r = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=30, params={
        "q": place if "delhi" in place.lower() else f"{place}, Delhi", "format": "json", "limit": 1,
        "viewbox": DELHI_VIEWBOX, "bounded": 1})
    r.raise_for_status()
    hits = r.json()
    if not hits:
        raise ValueError(f"could not find '{place}' in Delhi")
    return {"name": hits[0]["display_name"], "lat": float(hits[0]["lat"]), "lon": float(hits[0]["lon"])}


def _km(a_lat, a_lon, b_lat, b_lon) -> float:
    dy = (b_lat - a_lat) * 111.32
    dx = (b_lon - a_lon) * 111.32 * math.cos(math.radians(a_lat))
    return math.hypot(dx, dy)


def _slug(place: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in place.lower())


def nearby_sources(place: str, radius_km: float = 2.0) -> dict:
    """Mapped pollution sources near a place: construction sites, industry, landfills, power plants, big roads.

    Live from OpenStreetMap when its public servers answer. When they are busy, the saved snapshot for the
    station (scripts/build_osm_snapshot.py) is returned instead, marked with the date it was taken."""
    radius_km = max(0.5, min(float(radius_km), 5.0))
    try:
        return _nearby_live(place, radius_km)
    except (RuntimeError, requests.RequestException) as e:
        snap = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
        saved = snap.get("places", {}).get(_slug(place))
        if saved is None or radius_km != snap.get("radius_km"):
            raise
        return {**saved, "note": f"live map servers unavailable ({e}); this is the saved snapshot "
                                 f"from {snap['taken']}"}


def _nearby_live(place: str, radius_km: float) -> dict:
    # Mapped features change slowly, so answers are cached per place and radius (public servers are slow).
    cache = ROOT / "data" / "cache" / f"osm_{_slug(place)}_{radius_km:g}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    g = geocode(place)
    m = int(radius_km * 1000)
    q = f"""[out:json][timeout:20];
(
  way["landuse"="construction"](around:{m},{g['lat']},{g['lon']});
  way["landuse"="industrial"](around:{m},{g['lat']},{g['lon']});
  way["landuse"="landfill"](around:{m},{g['lat']},{g['lon']});
  nwr["power"="plant"](around:{m},{g['lat']},{g['lon']});
  way["highway"~"^(motorway|trunk)$"](around:{m},{g['lat']},{g['lon']});
);
out center tags;"""
    data = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": q}, headers=UA, timeout=25)
            if r.ok and r.text.lstrip().startswith("{"):
                data = r.json()
                break
        except requests.RequestException:
            continue
    if data is None:
        raise RuntimeError("OpenStreetMap (Overpass) is busy; try again in a minute")

    kinds = {"construction": [], "industrial": [], "landfill": [], "power_plant": [], "major_road": []}
    for el in data.get("elements", []):
        t = el.get("tags", {})
        c = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
        if c.get("lat") is None:
            continue
        kind = ("power_plant" if t.get("power") == "plant" else "major_road" if "highway" in t
                else t.get("landuse", "other"))
        if kind in kinds:
            kinds[kind].append({"name": t.get("name") or t.get("ref") or "(unnamed)",
                                "km": round(_km(g["lat"], g["lon"], c["lat"], c["lon"]), 2)})
    summary = {}
    for k, items in kinds.items():
        if k == "major_road":  # many segments per road: count distinct names
            names = sorted({i["name"] for i in items if i["name"] != "(unnamed)"})
            summary[k] = {"segments": len(items), "named": names[:10]}
        else:
            summary[k] = {"count": len(items), "nearest": sorted(items, key=lambda i: i["km"])[:6]}
    result = {"place": g["name"], "lat": g["lat"], "lon": g["lon"], "radius_km": radius_km,
              "source": "OpenStreetMap (mapped features; not a live permit list)", "sources": summary}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def station_snapshot(station: str, days: int = 7) -> dict:
    """Latest daily AQI readings for a station from the most recent finished pipeline run."""
    runs = sorted((p for p in (ROOT / "runs").glob("*") if (p / "daily.parquet").exists()),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        raise RuntimeError("no pipeline run with daily data yet")
    d = pd.read_parquet(runs[0] / "daily.parquet", columns=["station", "date", "aqi", "bucket", "PM2.5"])
    key = station.lower().replace(" ", "_")
    names = sorted(d["station"].astype(str).unique())
    match = next((n for n in names if key in n.lower()), None)
    if match is None:
        raise ValueError(f"no station matching '{station}'. Some options: {names[:8]}")
    cats = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    s = d[d["station"].astype(str) == match].sort_values("date").tail(days)
    return {"station": match, "run": runs[0].name, "days": [
        {"date": str(r.date)[:10], "aqi": None if pd.isna(r.aqi) else round(float(r.aqi)),
         "category": None if pd.isna(r.bucket) else cats[int(r.bucket)],
         "pm25": None if pd.isna(r._5) else round(float(r._5), 1)} for r in s.itertuples()]}


if __name__ == "__main__":  # quick manual check: python -m aqi.scout_tools "Anand Vihar"
    import sys
    place = sys.argv[1] if len(sys.argv) > 1 else "Anand Vihar"
    print(json.dumps(station_snapshot(place), indent=2))
