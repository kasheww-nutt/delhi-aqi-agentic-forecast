"""Daily ERA5 boundary-layer height for Delhi from the Open-Meteo archive API (no key needed).

Known gap (data gate E3): 2024-01-01 → 2024-06-30 is missing in Open-Meteo for every model; those
days stay empty and the models treat them as missing.

    python scripts/fetch_era5_blh.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "era5_delhi_blh.csv"
DELHI = (28.61, 77.21)


def main() -> None:
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=120, params={
        "latitude": DELHI[0], "longitude": DELHI[1], "start_date": "2018-01-01", "end_date": "2025-12-31",
        "hourly": "boundary_layer_height", "timezone": "Asia/Kolkata", "models": "era5"})
    r.raise_for_status()
    h = pd.DataFrame(r.json()["hourly"])
    h["date"] = pd.to_datetime(h["time"]).dt.normalize()
    daily = h.groupby("date")["boundary_layer_height"].agg(blh_mean="mean", blh_min="min").reset_index()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT, index=False)
    print(f"wrote {len(daily)} days ({daily.blh_mean.isna().sum()} missing) to {OUT}")


if __name__ == "__main__":
    main()
