"""Explainer: SHAP for tree models (rule-based) + a short LLM narration of the top drivers."""
from __future__ import annotations

import json
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..ledger import Ledger
from ..llm import LLM

NARRATOR = ("You are the explainer agent of a next-day AQI-category forecaster for Delhi. Given the "
            "mean |SHAP| importance of the top features (suffix _t0 = today, lagN = N days ago, _t1 = "
            "tomorrow's calendar or a forecast issued today), write 3-5 bullets on what drives tomorrow's "
            "category, in plain language for a viva panel. Flag anything that looks suspicious.")


def run(state: dict, ledger: Ledger) -> dict:
    bundle = pickle.load(open(state["paths"]["final_model"], "rb"))
    model, cols = bundle["model"], bundle["columns"]
    val = pd.read_parquet(state["paths"]["val"])
    sample = val[cols].sample(n=min(3000, len(val)), random_state=0)

    est = model.steps[-1][1] if hasattr(model, "steps") else model
    if not hasattr(est, "feature_importances_"):
        ledger.log("explainer", "info", f"{bundle['name']} is not a tree model; SHAP skipped")
        return {}
    import shap
    X = model[:-1].transform(sample) if hasattr(model, "steps") else sample
    sv = shap.TreeExplainer(est).shap_values(X)
    arr = np.abs(np.stack(sv, axis=-1) if isinstance(sv, list) else sv)  # (rows, features, classes)
    imp = pd.Series(arr.mean(axis=(0, 2)), index=cols).sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(8, 7))
    imp.head(20)[::-1].plot.barh(ax=ax, color="#4f81bd", title=f"Top drivers ({bundle['name']}, mean |SHAP|)")
    fig.tight_layout()
    fig.savefig(ledger.artifact("shap_importance.png"), dpi=130)
    plt.close(fig)
    imp.round(4).to_csv(ledger.artifact("shap_importance.csv"))

    notes = LLM(state["config"]["llm"], ledger).ask(NARRATOR, json.dumps(imp.head(15).round(4).to_dict()))
    if notes:
        ledger.artifact("explainer_notes.md").write_text(notes)
    ledger.log("explainer", "info", f"top drivers: {', '.join(imp.index[:5])}",
               artifacts=["shap_importance.png"] + (["explainer_notes.md"] if notes else []))
    return {}
