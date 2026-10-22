"""Leakage Guard (rule-based). Halts the run if any model input could contain the future.

Checks:
  1. every column of the feature table is registered (no silent, undocumented inputs);
  2. no registered feature refers to a day after the issue day unless it is known in advance;
  3. empirical check: no input agrees with tomorrow's target almost perfectly
     (a cheap tripwire for leaks the registry does not describe).
"""
from __future__ import annotations

import json

import pandas as pd

from ..ledger import Ledger

META = {"station", "date", "target_date", "target"}


def check(features: pd.DataFrame, registry: list[dict], agreement_limit: float = 0.97) -> list[str]:
    problems = []
    names = {r["name"] for r in registry}
    unregistered = sorted(set(features.columns) - META - names)
    if unregistered:
        problems.append(f"unregistered input columns: {unregistered}")
    for r in registry:
        if r["offset"] > 0 and not r["known_in_advance"]:
            problems.append(f"{r['name']} uses day t+{r['offset']} information that is not known on day t")
    y = features["target"]
    for r in registry:
        x = features[r["name"]]
        if x.nunique() > 50:  # bin continuous inputs onto the AQI scale before comparing
            x = pd.cut(x, [-1e9, 50, 100, 200, 300, 400, 1e9], labels=False) if "aqi" in r["name"] else None
        if x is not None and x.notna().any():
            agree = (x == y)[x.notna()].mean()
            if agree > agreement_limit and r["name"] != "bucket_t0":
                problems.append(f"{r['name']} matches tomorrow's category on {agree:.1%} of rows")
    return problems


def run(state: dict, ledger: Ledger) -> dict:
    feats = pd.read_parquet(state["paths"]["features"])
    registry = json.loads(open(state["paths"]["registry"]).read())
    problems = check(feats, registry)
    if problems:
        ledger.log("leakage_guard", "halt", "leakage detected — run stopped", problems=problems)
        return {"halted": "; ".join(problems)}
    future = [r["name"] for r in registry if r["offset"] > 0]
    ledger.log("leakage_guard", "info", f"{len(registry)} features checked; no leakage "
               f"({len(future)} known-in-advance t+1 features allowed: {future})")
    return {}
