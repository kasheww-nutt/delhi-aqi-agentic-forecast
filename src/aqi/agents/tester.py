"""Tester (rule-based). Runs ONCE: verifies the locked test hash, refits the best validated
configuration on train+val, and scores it and the persistence baseline on the test year."""
from __future__ import annotations

import json
import pickle

import pandas as pd

from ..ledger import Ledger
from ..metrics import evaluate
from .splitter import file_hash
from .trainer import active_columns, build_models


def run(state: dict, ledger: Ledger) -> dict:
    test_path = ledger.dir / "locked" / "test.parquet"
    if file_hash(test_path) != state["test_hash"]:
        ledger.log("tester", "halt", "locked test file changed since the split — refusing to evaluate")
        return {"halted": "test hash mismatch"}

    cfg, best = state["config"], state["best"]
    registry = json.loads(open(state["paths"]["registry"]).read())
    cols = active_columns(registry, best["feature_groups"])
    trval = pd.concat([pd.read_parquet(state["paths"]["train"]), pd.read_parquet(state["paths"]["val"])])
    test = pd.read_parquet(test_path)
    X, y = trval[cols], trval["target"].astype(int)

    one_cfg = {**cfg, "trainer": {**cfg["trainer"], "models": ["persistence", best["model"]]}}
    models = build_models(one_cfg, best["overrides"], X, y, trval["date"])
    results, fitted = {}, {}
    for name, (model, _) in models.items():
        fitted[name] = model.fit(X, y)
        results[name] = evaluate(test["target"], fitted[name].predict(test[cols]))

    preds = test[["station", "date", "target_date", "target"]].assign(
        pred=fitted[best["model"]].predict(test[cols]), persistence=fitted["persistence"].predict(test[cols]))
    preds.to_csv(ledger.artifact("test_predictions.csv"), index=False)
    with open(ledger.artifact("final_model.pkl"), "wb") as f:
        pickle.dump({"model": fitted[best["model"]], "columns": cols, "name": best["model"]}, f)

    m, p = results[best["model"]], results["persistence"]
    ledger.log("tester", "info", f"TEST 2025: {best['model']} macro-F1 {m['macro_f1']:.3f} vs persistence "
               f"{p['macro_f1']:.3f}; severe recall {m['severe_recall']:.2f} vs {p['severe_recall']:.2f}",
               results=results, artifacts=["test_predictions.csv"])
    return {"test_results": results, "paths": {**state["paths"], "final_model": str(ledger.artifact("final_model.pkl"))}}
