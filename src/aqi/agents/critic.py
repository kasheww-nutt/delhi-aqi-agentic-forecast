"""Critic (LLM with rule-based fallback). Reads validation results and picks ONE whitelisted action.

It never sees test data and cannot touch the split, the metric definitions or the class labels —
those are not in the action list. Stopping rules (iteration cap, minimum improvement) are enforced
in code, so the LLM cannot keep the loop running.
"""
from __future__ import annotations

import json

from ..ledger import Ledger
from ..llm import LLM

TOGGLEABLE = ["station_meteorology", "calendar", "city_context", "era5_blh", "cams_forecast"]
ACTIONS = (["widen_lgbm_search", "regularize_lgbm", "regularize_rf", "unweighted_classes", "STOP"]
           + [f"toggle:{g}" for g in TOGGLEABLE])

SYSTEM = """You are the critic agent in a leakage-free next-day AQI-category forecasting pipeline \
(6 ordinal CPCB categories, Delhi stations). You see validation-set results only. Diagnose the \
weakest point (overfitting, poor recall on Very Poor/Severe days, an unhelpful feature group, an \
under-tuned model) and choose exactly one action from the allowed list for the next training \
iteration, or STOP if further iterations are unlikely to help. Prefer actions that improve macro-F1 \
and severe-day recall. Never repeat an action that already failed to help."""

SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "action": {"type": "string", "enum": ACTIONS},
        "rationale": {"type": "string"},
    },
    "required": ["diagnosis", "action", "rationale"],
    "additionalProperties": False,
}


def rule_based(state: dict) -> dict:
    h = state["history"][-1]
    s = h["scores"][h["best_model"]]
    gap = s["train_macro_f1"] - s["macro_f1"]
    tried = {e.get("action") for e in state.get("history", [])}
    fix = {"lightgbm": ("regularize_lgbm", "raise min_child_samples, fewer leaves"),
           "random_forest": ("regularize_rf", "larger leaves and a depth limit")}.get(h["best_model"])
    if gap > 0.15 and fix and fix[0] not in tried:
        return {"diagnosis": f"{h['best_model']} train–val macro-F1 gap {gap:.2f} suggests overfitting",
                "action": fix[0], "rationale": fix[1]}
    margin = h["best_score"] - h["scores"]["persistence"]["macro_f1"]
    if (s["severe_recall"] < 0.6 or margin < 0.02) and "widen_lgbm_search" not in tried:
        return {"diagnosis": f"severe recall {s['severe_recall']:.2f}, only {margin:+.3f} over persistence",
                "action": "widen_lgbm_search", "rationale": "more Optuna trials and a larger search space"}
    built = {r["group"] for r in json.loads(open(state["paths"]["registry"]).read())}
    for g in ("cams_forecast", "era5_blh"):
        if g in built and not h["feature_groups"].get(g) and f"toggle:{g}" not in tried and margin < 0.02:
            return {"diagnosis": f"still only {margin:+.3f} over persistence; {g} is off",
                    "action": f"toggle:{g}", "rationale": f"try the {g} feature group (needs its data file)"}
    return {"diagnosis": "no rule fires", "action": "STOP", "rationale": "rule-based critic has no further ideas"}


def apply_action(action: str, state: dict) -> dict:
    groups = dict(state["feature_groups"])
    overrides = dict(state.get("trainer_overrides", {}))
    if action == "widen_lgbm_search":
        overrides["optuna_trials"] = 2 * overrides.get("optuna_trials", state["config"]["trainer"]["optuna_trials"])
        overrides["lgbm_space"] = {"max_estimators": 1200, "max_leaves": 127}
    elif action == "regularize_lgbm":
        overrides["lgbm_space"] = {**overrides.get("lgbm_space", {}), "max_leaves": 31, "min_child_lo": 60}
    elif action == "regularize_rf":
        overrides["rf"] = {"min_samples_leaf": 20, "max_depth": 14}
    elif action == "unweighted_classes":
        overrides["class_weight"] = None
    elif action.startswith("toggle:"):
        g = action.split(":", 1)[1]
        groups[g] = not groups.get(g, False)
    return {"feature_groups": groups, "trainer_overrides": overrides}


def run(state: dict, ledger: Ledger) -> dict:
    loop = state["config"]["loop"]
    hist = state["history"]
    improvement = hist[-1]["best_score"] - hist[-2]["best_score"] if len(hist) > 1 else None

    # Hard stopping rules, enforced in code.
    if state["iteration"] >= loop["max_iterations"]:
        decision = {"diagnosis": "iteration cap reached", "action": "STOP", "rationale": "budget", "by": "rule"}
    elif improvement is not None and improvement < loop["min_improvement"]:
        decision = {"diagnosis": f"last change moved val macro-F1 by {improvement:+.3f}", "action": "STOP",
                    "rationale": f"below the {loop['min_improvement']} threshold", "by": "rule"}
    else:
        built = {r["group"] for r in json.loads(open(state["paths"]["registry"]).read())}
        allowed = [a for a in ACTIONS if not a.startswith("toggle:") or a.split(":", 1)[1] in built]
        schema = {**SCHEMA, "properties": {**SCHEMA["properties"],
                                           "action": {"type": "string", "enum": allowed}}}
        summary = {
            "iteration": state["iteration"],
            "history": [{"iteration": e["iteration"], "action_chosen_after": e.get("action"),
                         "best_model": e["best_model"], "best_val_macro_f1": e["best_score"],
                         "scores": {n: {k: v for k, v in s.items() if k != "confusion"}
                                    for n, s in e["scores"].items()}} for e in hist],
            "feature_groups": state["feature_groups"],
            "groups_without_data": [g for g in TOGGLEABLE if g not in built],
            "category_order": ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"],
            "allowed_actions": allowed,
        }
        llm = LLM(state["config"]["llm"], ledger)
        decision = llm.ask(SYSTEM, json.dumps(summary, default=str), schema)
        if decision and decision.get("action") in allowed:
            decision["by"] = f"llm ({llm.answered_by})"
        else:
            decision = {**rule_based(state), "by": f"rule (llm: {llm.disabled_reason or 'invalid answer'})"}

    hist[-1]["action"] = decision["action"]
    update = {"critic_decision": decision, "history": hist}
    if decision["action"] != "STOP":
        update.update(apply_action(decision["action"], state))
    ledger.log("critic", "info", f"{decision['action']} — {decision['diagnosis']}",
               iteration=state["iteration"], decision=decision)
    return update


def route(state: dict) -> str:
    return "tester" if state["critic_decision"]["action"] == "STOP" else "trainer"
