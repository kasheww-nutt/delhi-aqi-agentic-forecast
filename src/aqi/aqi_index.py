"""CPCB National AQI: sub-indices, overall AQI and the six categories.

Breakpoints follow the CPCB National Air Quality Index (2014). PM10, PM2.5, NO2, SO2 and NH3 use
24-hour averages; CO and O3 use the maximum 8-hour average of the day. The overall AQI is the
maximum sub-index, valid only when at least three pollutants (one of them PM2.5 or PM10) are present.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BUCKETS = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
AQI_EDGES = [0, 50, 100, 200, 300, 400, 500]

# (concentration breakpoints) mapped onto AQI_EDGES; last value is the cap used for "Severe".
BREAKPOINTS = {
    "PM10":  [0, 50, 100, 250, 350, 430, 510],
    "PM2.5": [0, 30, 60, 90, 120, 250, 380],
    "NO2":   [0, 40, 80, 180, 280, 400, 520],
    "SO2":   [0, 40, 80, 380, 800, 1600, 2400],
    "NH3":   [0, 200, 400, 800, 1200, 1800, 2400],
    "CO":    [0, 1.0, 2.0, 10, 17, 34, 51],      # mg/m3, 8-h max
    "Ozone": [0, 50, 100, 168, 208, 748, 1028],  # ug/m3, 8-h max
}


def sub_index(pollutant: str, conc: pd.Series) -> pd.Series:
    bp = BREAKPOINTS[pollutant]
    clipped = conc.clip(lower=0, upper=bp[-1])
    return pd.Series(np.interp(clipped, bp, AQI_EDGES), index=conc.index).where(conc.notna())


def overall_aqi(sub: pd.DataFrame) -> pd.Series:
    """sub: one column per pollutant sub-index."""
    n_valid = sub.notna().sum(axis=1)
    has_pm = sub[[c for c in ("PM2.5", "PM10") if c in sub]].notna().any(axis=1)
    return sub.max(axis=1).where((n_valid >= 3) & has_pm)


def bucket(aqi: pd.Series) -> pd.Series:
    """AQI value → ordinal class 0..5 (Good..Severe); NaN stays NaN."""
    codes = pd.cut(aqi, bins=[-np.inf, 50, 100, 200, 300, 400, np.inf], labels=False)
    return pd.Series(codes, index=aqi.index, dtype="float")
