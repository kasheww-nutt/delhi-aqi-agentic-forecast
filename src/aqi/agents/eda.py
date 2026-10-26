"""EDA agent: rule-based plots + an LLM narrator that only ever sees summary statistics."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ..ledger import Ledger
from ..llm import LLM
from .ingestion import KEEP

NARRATOR = ("You are the EDA agent in an air-quality forecasting pipeline. You receive summary "
            "statistics of hourly CPCB data from Delhi stations. Write 4-6 short bullet observations a "
            "student team should know before modelling (seasonality, diurnal cycle, missingness, outliers, "
            "station differences). Only state what the numbers support.")


def run(state: dict, ledger: Ledger) -> dict:
    h = pd.read_parquet(state["paths"]["hourly"])
    h = h[h.station.astype(str).isin(state["stations"])]
    h["month"] = h.timestamp.dt.month
    h["hour"] = h.timestamp.dt.hour

    missing = h.groupby("station", observed=True)[KEEP].apply(lambda g: g.isna().mean() * 100)
    monthly = h.groupby("month")["PM2.5"].median()
    winter = h[h.month.isin([11, 12, 1])].groupby("hour")["PM2.5"].median()
    by_station = h.groupby("station", observed=True)["PM2.5"].median().sort_values()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax = axes[0, 0]
    ax.imshow(missing.values, aspect="auto", cmap="magma_r", vmin=0, vmax=100)
    ax.set_xticks(range(len(KEEP)), KEEP, rotation=90, fontsize=7)
    ax.set_yticks([]); ax.set_ylabel("stations"); ax.set_title("Missing hours (%) per station × variable")
    monthly.plot.bar(ax=axes[0, 1], color="#c0504d", title="Median PM2.5 by month (µg/m³)")
    winter.plot(ax=axes[1, 0], marker="o", title="Winter (Nov–Jan) median PM2.5 by hour (IST)")
    by_station.plot.barh(ax=axes[1, 1], fontsize=5, title="Median PM2.5 by station")
    fig.tight_layout()
    fig.savefig(ledger.artifact("eda_overview.png"), dpi=120)
    plt.close(fig)

    stats = {
        "stations": len(state["stations"]),
        "rows": len(h),
        "pm25_median_by_month": monthly.round(0).to_dict(),
        "winter_pm25_median_by_hour": winter.round(0).to_dict(),
        "pm25_quantiles": h["PM2.5"].quantile([.01, .5, .99, .999, 1]).round(1).to_dict(),
        "pct_missing_overall": h[KEEP].isna().mean().mul(100).round(1).to_dict(),
        "cleanest_station": str(by_station.index[0]), "dirtiest_station": str(by_station.index[-1]),
    }
    ledger.artifact("eda_stats.json").write_text(json.dumps(stats, indent=2, default=str))

    llm = LLM(state["config"]["llm"], ledger, "eda")
    notes = llm.ask(NARRATOR, json.dumps(stats, default=str))
    if notes:
        ledger.artifact("eda_notes.md").write_text(notes, encoding="utf-8")
    ledger.log("eda", "info",
               f"peak month {int(monthly.idxmax())}, winter peak hour {int(winter.idxmax())}:00 IST",
               narrated_by=f"llm ({llm.answered_by})" if notes else f"none ({llm.disabled_reason})",
               artifacts=["eda_overview.png", "eda_stats.json"] + (["eda_notes.md"] if notes else []))
    return {}
