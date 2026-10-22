"""Ingestion agent (rule-based): station-year CSVs → one hourly panel (station × hour)."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import resolve
from ..ledger import Ledger

KEEP = ["PM2.5", "PM10", "NO", "NO2", "NOx", "NH3", "SO2", "CO", "Ozone", "Benzene", "Toluene",
        "AT", "RH", "WS", "WD", "RF", "SR", "BP"]
FILE_RE = re.compile(r"site_(\d+)_(.+)_1Hr\.csv")


def _read_station_year(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, low_memory=False)
    short = {c: c.split(" (")[0] for c in raw.columns}
    raw = raw.rename(columns=short)
    out = pd.DataFrame({"timestamp": pd.to_datetime(raw["Timestamp"], errors="coerce")})
    for col in KEEP:
        # Blank cells and non-numeric placeholders become NaN (README caveat).
        out[col] = pd.to_numeric(raw[col], errors="coerce").astype("float32") if col in raw else np.float32(np.nan)
    site, name = FILE_RE.match(path.name).groups()
    out["station"] = f"{site}_{name}"
    return out.dropna(subset=["timestamp"])


def _from_canonical(path: str, y0: int, y1: int) -> pd.DataFrame:
    """A dataset the schema adapter already mapped onto the canonical schema."""
    h = pd.read_parquet(path)
    h = h[h.timestamp.dt.year.between(y0, y1)].copy()
    for col in KEEP:
        if col not in h:
            h[col] = np.float32(np.nan)
    return h[["timestamp", *KEEP, "station"]]


def run(state: dict, ledger: Ledger) -> dict:
    cfg = state["config"]["data"]
    y0, y1 = cfg["years"]
    if "canonical" in state.get("paths", {}):
        hourly = _from_canonical(state["paths"]["canonical"], y0, y1)
        hourly["station"] = hourly["station"].astype("category")
        out = ledger.dir / "hourly.parquet"
        hourly.to_parquet(out, index=False)
        ledger.log("ingestion", "info", f"adapted dataset: {hourly.station.nunique()} stations, {len(hourly):,} "
                   f"{state.get('granularity', 'hourly')} rows ({y0}–{y1})",
                   metrics={"stations": int(hourly.station.nunique()), "rows": len(hourly)})
        return {"paths": {**state["paths"], "hourly": str(out)}}

    root = resolve(cfg["cpcb_dir"])
    files = sorted(p for y in range(y0, y1 + 1) for p in (root / str(y)).glob("site_*_1Hr.csv"))
    if not files:
        raise FileNotFoundError(f"No station files under {root}; download the Kaggle dataset first.")

    hourly = pd.concat([_read_station_year(f) for f in files], ignore_index=True)
    hourly["station"] = hourly["station"].astype("category")
    out = ledger.dir / "hourly.parquet"
    hourly.to_parquet(out, index=False)

    ledger.log("ingestion", "info", f"{len(files)} station-year files, {hourly.station.nunique()} stations, "
               f"{len(hourly):,} hourly rows ({y0}–{y1})",
               metrics={"files": len(files), "stations": int(hourly.station.nunique()), "rows": len(hourly)})
    return {"paths": {**state.get("paths", {}), "hourly": str(out)}}
