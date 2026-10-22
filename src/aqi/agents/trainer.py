"""Trainer (tools: scikit-learn, LightGBM, Optuna). The critic chooses *what* to try; this agent
only executes it.

Models: B0 persistence, M1 multinomial logistic regression, M2 random forest, M3 LightGBM (tuned).
Hyperparameters are tuned on an inner hold-out (the last training year), never on validation,
so validation stays an honest signal for the critic.
"""
from __future__ import annotations

import json
import pickle

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..ledger import Ledger
from ..metrics import LABELS

optuna.logging.set_verbosity(optuna.logging.WARNING)


def active_columns(registry: list[dict], groups: dict[str, bool]) -> list[str]:
    return [r["name"] for r in registry if groups.get(r["group"], False)]


class Persistence:
    """B0: tomorrow's category = today's category."""
    def fit(self, X, y):
        return self

    def predict(self, X):
        return X["bucket_t0"].fillna(2).to_numpy(int)


def _lgbm(params: dict, seed: int, class_weight):
    return lgb.LGBMClassifier(objective="multiclass", num_class=6, class_weight=class_weight,
                              random_state=seed, verbose=-1, n_jobs=-1, **params)


def tune_lgbm(X, y, dates, seed, trials, class_weight, space) -> dict:
    inner = dates >= dates.max() - pd.Timedelta(days=365)
    Xa, ya, Xb, yb = X[~inner], y[~inner], X[inner], y[inner]

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 150, space["max_estimators"]),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 8, space["max_leaves"]),
            "min_child_samples": trial.suggest_int("min_child_samples", space["min_child_lo"], 200),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0), "subsample_freq": 1,
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        }
        m = _lgbm(params, seed, class_weight).fit(Xa, ya)
        return f1_score(yb, m.predict(Xb), labels=LABELS, average="macro", zero_division=0)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials)
    return {**study.best_params, "subsample_freq": 1}


def build_models(cfg: dict, overrides: dict, X, y, dates) -> dict:
    seed = cfg["seed"]
    cw = overrides.get("class_weight", cfg["trainer"]["class_weight"])
    space = {"max_estimators": 600, "max_leaves": 63, "min_child_lo": 10, **overrides.get("lgbm_space", {})}
    trials = overrides.get("optuna_trials", cfg["trainer"]["optuna_trials"])
    models = {}
    for name in cfg["trainer"]["models"]:
        if name == "persistence":
            models[name] = (Persistence(), {})
        elif name == "logreg":
            models[name] = (make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                          LogisticRegression(max_iter=3000, class_weight=cw, C=1.0)), {})
        elif name == "random_forest":
            models[name] = (make_pipeline(SimpleImputer(strategy="median"),
                                          RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                                                 class_weight="balanced_subsample" if cw else None,
                                                                 n_jobs=-1, random_state=seed)), {})
        elif name == "lightgbm":
            params = tune_lgbm(X, y, dates, seed, trials, cw, space)
            models[name] = (_lgbm(params, seed, cw), params)
    return models


def run(state: dict, ledger: Ledger) -> dict:
    cfg = state["config"]
    it = state.get("iteration", 0) + 1
    registry = json.loads(open(state["paths"]["registry"]).read())
    cols = active_columns(registry, state["feature_groups"])
    train = pd.read_parquet(state["paths"]["train"])
    X, y = train[cols], train["target"].astype(int)
    overrides = state.get("trainer_overrides", {})

    models = build_models(cfg, overrides, X, y, train["date"])
    fitted, params = {}, {}
    for name, (model, p) in models.items():
        fitted[name] = model.fit(X, y)
        params[name] = p
    path = ledger.artifact(f"models_iter{it}.pkl")
    with open(path, "wb") as f:
        pickle.dump({"models": fitted, "columns": cols}, f)

    ledger.log("trainer", "info", f"iteration {it}: trained {list(fitted)} on {len(cols)} features "
               f"× {len(X):,} rows", iteration=it, params=params, overrides=overrides,
               feature_groups=state["feature_groups"])
    return {"iteration": it, "feature_columns": cols,
            "paths": {**state["paths"], "models": str(path)}}
