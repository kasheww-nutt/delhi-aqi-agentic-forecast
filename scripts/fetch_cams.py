"""Download CAMS global day-ahead PM2.5 forecasts for Delhi and build a daily feature file.

For each 00 UTC run issued on day t, lead times 19–42 h cover day t+1 in IST (UTC+5:30). The
2×2 CAMS cells over Delhi (0.4°) are averaged into one city-scale series.

Needs ~/.cdsapirc for the Atmosphere Data Store and the dataset's CC-BY licence accepted.
About 1.5 min per month → ~2.5 h for 2018–2025; months already on disk are skipped.

    python scripts/fetch_cams.py --start 2018-01 --end 2025-12
"""
from __future__ import annotations

import argparse
import calendar
import sys
import zipfile
from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "cams"
AREA = [29.0, 76.8, 28.3, 77.5]  # N, W, S, E


def fetch_month(client, y: int, m: int) -> Path:
    target = OUT / f"cams_{y}{m:02d}.zip"
    if target.exists():
        return target
    last = calendar.monthrange(y, m)[1]
    client.retrieve("cams-global-atmospheric-composition-forecasts", {
        "variable": ["particulate_matter_2.5um"],
        "date": [f"{y}-{m:02d}-01/{y}-{m:02d}-{last}"],
        "time": ["00:00"],
        "leadtime_hour": [str(h) for h in range(19, 43)],
        "type": ["forecast"],
        "area": AREA,
        "data_format": "netcdf_zip",
    }, str(target))
    return target


def to_daily(zip_path: Path) -> pd.DataFrame:
    folder = zip_path.with_suffix("")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(folder)
    ds = xr.open_dataset(next(folder.glob("*.nc")))
    pm = (ds["pm2p5"] * 1e9).mean(dim=["latitude", "longitude"])  # kg/m3 → µg/m3, city mean
    df = pm.to_dataframe(name="pm25").reset_index()
    df["issue_date"] = pd.to_datetime(df["forecast_reference_time"]).dt.normalize()
    return (df.groupby("issue_date")["pm25"].agg(cams_pm25_tomorrow_mean="mean", cams_pm25_tomorrow_max="max")
            .reset_index())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01")
    ap.add_argument("--end", default="2025-12")
    args = ap.parse_args()
    import cdsapi

    OUT.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client(quiet=True)
    frames = []
    for period in pd.period_range(args.start, args.end, freq="M"):
        path = fetch_month(client, period.year, period.month)
        frames.append(to_daily(path))
        print(f"{period}: ok", flush=True)
    daily = pd.concat(frames).sort_values("issue_date").drop_duplicates("issue_date")
    daily.to_csv(OUT / "cams_daily_delhi.csv", index=False)
    print(f"wrote {len(daily)} days to {OUT / 'cams_daily_delhi.csv'}")


if __name__ == "__main__":
    sys.exit(main())
