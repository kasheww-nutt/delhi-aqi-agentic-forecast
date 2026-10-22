"""Evaluator (rule-based): scores every model of the current iteration on VALIDATION only."""
from __future__ import annotations

import pickle

import pandas as pd

from ..ledger import Ledger
from ..metrics import evaluate


def run(state: dict, ledger: Ledger) -> dict:
    primary = state["config"]["loop"]["primary_metric"]
    bundle = pickle.load(open(state["paths"]["models"], "rb"))
    train = pd.read_parquet(state["paths"]["train"])
    val = pd.read_parquet(state["paths"]["val"])
    cols = bundle["columns"]

    scores = {}
    for name, model in bundle["models"].items():
        m = evaluate(val["target"], model.predict(val[cols]))
        m["train_macro_f1"] = evaluate(train["target"], model.predict(train[cols]))["macro_f1"]
        scores[name] = m
    best_name = max((n for n in scores if n != "persistence"), key=lambda n: scores[n][primary])

    entry = {"iteration": state["iteration"], "scores": scores, "best_model": best_name,
             "best_score": scores[best_name][primary],
             "feature_groups": state["feature_groups"], "overrides": state.get("trainer_overrides", {})}
    history = state.get("history", []) + [entry]
    best = state.get("best")
    if best is None or entry["best_score"] > best["score"]:
        best = {"iteration": entry["iteration"], "model": best_name, "score": entry["best_score"],
                "models_path": state["paths"]["models"], "feature_groups": dict(state["feature_groups"]),
                "overrides": dict(state.get("trainer_overrides", {}))}

    table = {n: {k: s[k] for k in ("macro_f1", "severe_recall", "accuracy", "within_one_category",
                                   "train_macro_f1")} for n, s in scores.items()}
    ledger.log("evaluator", "info", f"iteration {state['iteration']}: best {best_name} "
               f"val {primary}={entry['best_score']:.3f} (persistence {scores['persistence'][primary]:.3f})",
               iteration=state["iteration"], scores=table)
    return {"history": history, "best": best}
