"""Feature builder (rule-based). Every feature is registered with its time offset.

Row = (station, issue day t). Target = AQI bucket on day t+1 at the same station.
`offset` is the day the information refers to relative to t; anything with offset > 0 must be
`known_in_advance` (calendar facts, a forecast issued on day t) or the Leakage Guard halts the run.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import resolve
from ..ledger import Ledger

# Diwali (Lakshmi Puja) dates — fireworks spike PM2.5 for ~2 days around them.
DIWALI = ["2015-11-11", "2016-10-30", "2017-10-19", "2018-11-07", "2019-10-27", "2020-11-14", "2021-11-04", "2022-10-24", "2023-11-12",
          "2024-10-31", "2025-10-20"]
POLLUTANTS = ["PM2.5", "PM10", "NO2", "CO", "Ozone", "SO2", "NH3"]
MET = ["AT", "RH", "WS", "WD_sin", "WD_cos", "RF", "SR", "BP"]


class Registry:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, df: pd.DataFrame, name: str, values, group: str, offset: int, known_in_advance=False):
        df[name] = values
        self.items.append({"name": name, "group": group, "offset": offset,
                           "known_in_advance": known_in_advance})


def _era5(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    e = pd.read_csv(path, parse_dates=["date"])
    return e[["date", "blh_mean", "blh_min"]]


def _cams(cams_dir: Path) -> pd.DataFrame | None:
    f = cams_dir / "cams_daily_delhi.csv"   # written by scripts/fetch_cams.py
    if not f.exists():
        return None
    c = pd.read_csv(f, parse_dates=["issue_date"])
    return c.rename(columns={"issue_date": "date"})[["date", "cams_pm25_tomorrow_mean", "cams_pm25_tomorrow_max"]]


def run(state: dict, ledger: Ledger) -> dict:
    cfg = state["config"]
    fcfg = cfg["features"]
    d = pd.read_parquet(state["paths"]["daily"]).sort_values(["station", "date"]).reset_index(drop=True)
    d["station"] = d["station"].astype(str)
    reg = Registry()
    g = d.groupby("station")

    # Target: tomorrow's observed bucket (requires tomorrow to be the next calendar day).
    nxt_date = g["date"].shift(-1)
    d["target"] = g["bucket"].shift(-1).where(nxt_date == d["date"] + pd.Timedelta(days=1))
    d["target_date"] = d["date"] + pd.Timedelta(days=1)

    # Pollutant history (offset ≤ 0).
    for p in [p for p in POLLUTANTS if p in d]:
        reg.add(d, f"{p}_t0", d[p], "pollutant_history", 0)
    reg.add(d, "aqi_t0", d["aqi_f"], "pollutant_history", 0)
    reg.add(d, "bucket_t0", d["bucket"].fillna(pd.cut(d["aqi_f"], [-1, 50, 100, 200, 300, 400, 1e9],
                                                       labels=False)), "pollutant_history", 0)
    for lag in fcfg["lags"]:
        reg.add(d, f"aqi_lag{lag}", g["aqi_f"].shift(lag), "pollutant_history", -lag)
        reg.add(d, f"pm25_lag{lag}", g["PM2.5"].shift(lag), "pollutant_history", -lag)
    for w in fcfg["rolling_windows"]:
        roll = g["aqi_f"].rolling(w, min_periods=max(2, w - 1))
        reg.add(d, f"aqi_roll{w}_mean", roll.mean().reset_index(level=0, drop=True), "pollutant_history", 0)
        reg.add(d, f"aqi_roll{w}_std", roll.std().reset_index(level=0, drop=True), "pollutant_history", 0)
    reg.add(d, "aqi_delta1", d["aqi_t0"] - d["aqi_lag1"], "pollutant_history", 0)
    reg.add(d, "n_missing_inputs_t0", d["n_missing_inputs"], "pollutant_history", 0)
    reg.add(d, "pm25_missing_t0", d["pm25_missing"], "pollutant_history", 0)

    # On-site meteorology on day t.
    for m in [m for m in MET if m in d]:
        reg.add(d, f"{m}_t0", d[m], "station_meteorology", 0)

    # Calendar facts about tomorrow are known in advance.
    td = d["target_date"]
    reg.add(d, "dow_t1", td.dt.dayofweek, "calendar", 1, True)
    reg.add(d, "doy_sin_t1", np.sin(2 * np.pi * td.dt.dayofyear / 365.25), "calendar", 1, True)
    reg.add(d, "doy_cos_t1", np.cos(2 * np.pi * td.dt.dayofyear / 365.25), "calendar", 1, True)
    diwali = pd.to_datetime(DIWALI)
    days_to = td.apply(lambda x: int(np.min(np.abs((diwali - x).days))))
    reg.add(d, "diwali_window_t1", (days_to <= 2).astype("int8"), "calendar", 1, True)
    lo, hi = cfg["split"]["lockdown"]
    reg.add(d, "lockdown_t0", d["date"].between(lo, hi).astype("int8"), "calendar", 0)

    # City-wide context on day t (all stations' readings are public on day t).
    city = d.groupby("date")["aqi_f"].agg(["mean", "max"])
    reg.add(d, "city_aqi_mean_t0", d["date"].map(city["mean"]), "city_context", 0)
    reg.add(d, "city_aqi_max_t0", d["date"].map(city["max"]), "city_context", 0)
    reg.add(d, "station_minus_city_t0", d["aqi_f"] - d["city_aqi_mean_t0"], "city_context", 0)

    available = {k: v for k, v in fcfg["groups"].items()}
    era5 = _era5(resolve(cfg["data"]["era5_file"])) if available.get("era5_blh") else None
    if era5 is not None:
        d = d.merge(era5, on="date", how="left")
        for c in ("blh_mean", "blh_min"):
            reg.add(d, f"{c}_t0", d.pop(c), "era5_blh", 0)
        reg.add(d, "ventilation_t0", d["blh_mean_t0"] * d.get("WS_t0", np.nan), "era5_blh", 0)
    else:
        available["era5_blh"] = False
    cams = _cams(resolve(cfg["data"]["cams_dir"])) if available.get("cams_forecast") else None
    if cams is not None:
        d = d.merge(cams, on="date", how="left")   # forecast issued on day t, valid for t+1
        for c in ("cams_pm25_tomorrow_mean", "cams_pm25_tomorrow_max"):
            reg.add(d, c, d.pop(c), "cams_forecast", 1, True)
    else:
        available["cams_forecast"] = False

    if fcfg.get("leaky_demo"):
        # Deliberately leaky: tomorrow's observed PM2.5. The Leakage Guard must stop the run.
        reg.add(d, "pm25_t1_LEAK", g["PM2.5"].shift(-1), "leaky_demo", 1, False)
        available["leaky_demo"] = True

    d = d[d["target"].notna()].reset_index(drop=True)
    keep = ["station", "date", "target_date", "target"] + [i["name"] for i in reg.items]
    out = ledger.dir / "features.parquet"
    d[keep].to_parquet(out, index=False)
    (ledger.dir / "feature_registry.json").write_text(json.dumps(reg.items, indent=2))

    counts = pd.Series([i["group"] for i in reg.items]).value_counts().to_dict()
    skipped = [k for k, v in fcfg["groups"].items() if v and not available.get(k)]
    ledger.log("features", "info", f"{len(reg.items)} features on {len(d):,} rows; groups {counts}",
               skipped_groups=skipped, metrics={"features": len(reg.items), "rows": len(d)})
    return {"paths": {**state["paths"], "features": str(out),
                      "registry": str(ledger.dir / "feature_registry.json")},
            "feature_groups": {k: bool(v) for k, v in available.items()}}
