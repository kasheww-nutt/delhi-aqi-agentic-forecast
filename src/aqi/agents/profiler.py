"""Profiler agent (rule-based): coverage per station-year, decides which stations are usable."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ..ledger import Ledger
from .ingestion import KEEP


def run(state: dict, ledger: Ledger) -> dict:
    cfg = state["config"]["profiler"]
    hourly = pd.read_parquet(state["paths"]["hourly"])
    hourly["year"] = hourly.timestamp.dt.year
    hours = hourly.groupby(["station", "year"], observed=True).size()

    coverage = (hourly.groupby(["station", "year"], observed=True)[KEEP].count()
                .div(hours, axis=0).mul(100).round(1))
    pm = coverage["PM2.5"].unstack("year")
    years_ok = (pm >= cfg["min_pm25_coverage"]).sum(axis=1)
    keep = sorted(years_ok[years_ok >= cfg["min_years_meeting_coverage"]].index.astype(str))
    dropped = sorted(set(pm.index.astype(str)) - set(keep))

    coverage.to_csv(ledger.artifact("coverage_station_year.csv"))
    fig, ax = plt.subplots(figsize=(10, 9))
    im = ax.imshow(pm.values, aspect="auto", cmap="viridis", vmin=0, vmax=100)
    ax.set_yticks(range(len(pm)), [s[:28] for s in pm.index.astype(str)], fontsize=6)
    ax.set_xticks(range(len(pm.columns)), pm.columns)
    ax.set_title("PM2.5 hourly coverage (%) by station and year")
    fig.colorbar(im, ax=ax, shrink=0.6)
    fig.tight_layout()
    fig.savefig(ledger.artifact("coverage_heatmap.png"), dpi=130)
    plt.close(fig)

    profile = {"stations_total": int(len(pm)), "stations_kept": len(keep), "dropped": dropped,
               "median_coverage_by_year": coverage.groupby("year").median().round(0).to_dict()}
    ledger.artifact("profile.json").write_text(json.dumps(profile, indent=2))
    ledger.log("profiler", "info", f"kept {len(keep)}/{len(pm)} stations "
               f"(PM2.5 ≥{cfg['min_pm25_coverage']}% in ≥{cfg['min_years_meeting_coverage']} years)",
               metrics={"stations_kept": len(keep), "dropped": dropped},
               artifacts=["coverage_heatmap.png", "profile.json"])
    return {"stations": keep}
