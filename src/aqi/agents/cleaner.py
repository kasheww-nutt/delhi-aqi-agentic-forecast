"""Cleaner agent (rule-based, config-driven). Every decision it takes is written to the ledger.

Hourly → cleaned hourly → daily station panel with:
  * `aqi` / `bucket`      — from *observed* data only (used for targets; never imputed)
  * `aqi_f` and features  — from imputed data (used as inputs)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..aqi_index import BREAKPOINTS, bucket, overall_aqi, sub_index
from ..ledger import Ledger
from .ingestion import KEEP

MEAN_24H = ["PM2.5", "PM10", "NO2", "SO2", "NH3"]
MAX_8H = ["CO", "Ozone"]


def _daily(h: pd.DataFrame, cols: list[str], min_hours: int, daily_input: bool = False) -> pd.DataFrame:
    h = h.assign(date=h.timestamp.dt.normalize())
    g = h.groupby(["station", "date"], observed=True)
    if daily_input:  # source already reports daily values (one row per station-day)
        min_hours = 1
    mean_cols = [c for c in cols if c not in ("WD", "RF", *([] if daily_input else MAX_8H))]
    daily = g[mean_cols].mean().where(g[mean_cols].count() >= min_hours)
    if "RF" in cols:
        daily["RF"] = g["RF"].sum(min_count=min_hours)
    if "WD" in cols:  # wind direction: average the unit vector, not the angle
        rad = np.deg2rad(h["WD"])
        h["WD_sin"], h["WD_cos"] = np.sin(rad), np.cos(rad)
        g = h.groupby(["station", "date"], observed=True)
        daily[["WD_sin", "WD_cos"]] = g[["WD_sin", "WD_cos"]].mean()
    for c in [c for c in MAX_8H if c in cols and not daily_input]:
        roll = h.groupby("station", observed=True)[c].transform(lambda s: s.rolling(8, min_periods=6).mean())
        daily[c] = roll.groupby([h.station, h.date], observed=True).max()
    return daily.reset_index()


def _aqi(daily: pd.DataFrame) -> pd.Series:
    subs = pd.DataFrame({p: sub_index(p, daily[p]) for p in BREAKPOINTS if p in daily})
    return overall_aqi(subs)


def run(state: dict, ledger: Ledger) -> dict:
    cfg = state["config"]["cleaner"]
    train_end = pd.Timestamp(state["config"]["split"]["train"][1])
    h = pd.read_parquet(state["paths"]["hourly"])
    h = h[h.station.astype(str).isin(state["stations"])].sort_values(["station", "timestamp"])
    decisions = []

    # 1. Physically impossible values → missing; instrument ceiling → capped and counted.
    num = [c for c in KEEP if c in h]
    negatives = int((h[num] < 0).sum().sum())
    h[num] = h[num].mask(h[num] < 0)
    at_ceiling = int((h["PM2.5"] >= cfg["pm25_ceiling"]).sum())
    h["PM2.5"] = h["PM2.5"].clip(upper=cfg["pm25_ceiling"])
    decisions.append(f"{negatives} negative readings set to missing; {at_ceiling} PM2.5 readings at the "
                     f"{cfg['pm25_ceiling']} µg/m³ instrument ceiling kept as censored values")

    # 2. Drop variables that are mostly missing across the whole panel.
    miss = h[num].isna().mean() * 100
    dropped = sorted(miss[miss > cfg["drop_column_if_missing_over"]].index)
    kept = [c for c in num if c not in dropped]
    decisions.append(f"dropped {dropped or 'no'} columns (> {cfg['drop_column_if_missing_over']}% missing)")

    # 3. Short gaps: linear interpolation within each station, never across long outages.
    daily_input = state.get("granularity") == "daily"
    if daily_input:
        decisions.append("source is daily: no hourly interpolation, daily values used as reported")
    else:
        h[kept] = (h.groupby("station", observed=True)[kept]
                   .transform(lambda s: s.interpolate(limit=cfg["short_gap_hours"], limit_area="inside")))
        decisions.append(f"interpolated gaps ≤ {cfg['short_gap_hours']} h within each station")

    # 4. Daily aggregation (CPCB averaging rules) and AQI from observed data.
    daily = _daily(h, kept, cfg["daily_min_hours"], daily_input)
    daily["aqi"] = _aqi(daily)
    daily["bucket"] = bucket(daily["aqi"])
    if not daily_input:
        decisions.append(f"daily means need ≥ {cfg['daily_min_hours']} valid hours; CO/O3 use the max 8-h mean")

    # 5. Long gaps in *inputs*: station-month medians learned from the training period only.
    feat_cols = [c for c in daily.columns if c not in ("station", "date", "aqi", "bucket")]
    daily["n_missing_inputs"] = daily[feat_cols].isna().sum(axis=1)
    daily["pm25_missing"] = daily["PM2.5"].isna().astype("int8")
    if cfg["imputation"] == "station_month_median":
        month = daily.date.dt.month
        medians = (daily[daily.date <= train_end].groupby([daily.station, month], observed=True)[feat_cols]
                   .median())
        fill = medians.reindex(pd.MultiIndex.from_arrays([daily.station, month])).set_axis(daily.index)
        daily[feat_cols] = daily[feat_cols].fillna(fill)
        decisions.append("remaining input gaps filled with station-month medians computed on 2018–2022 "
                         "(train) only, with a missing-count and PM2.5-missing flag")
    daily["aqi_f"] = _aqi(daily)

    out = ledger.dir / "daily.parquet"
    daily.to_parquet(out, index=False)
    ledger.log("cleaner", "info", f"{len(daily):,} station-days; target available on "
               f"{daily.bucket.notna().mean():.1%}", decisions=decisions,
               metrics={"station_days": len(daily), "dropped_columns": dropped,
                        "bucket_distribution": daily.bucket.value_counts().sort_index().to_dict()})
    return {"paths": {**state["paths"], "daily": str(out)}}
