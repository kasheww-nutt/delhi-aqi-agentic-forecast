from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

LABELS = list(range(6))
SEVERE = {4, 5}  # Very Poor + Severe: the classes that trigger health advisories


def evaluate(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, int), np.asarray(y_pred, int)
    is_sev = np.isin(y_true, list(SEVERE))
    return {
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="weighted", zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "severe_recall": round(float(np.isin(y_pred[is_sev], list(SEVERE)).mean()) if is_sev.any() else float("nan"), 4),
        "within_one_category": round(float((np.abs(y_true - y_pred) <= 1).mean()), 4),
        "mean_category_error": round(float(np.abs(y_true - y_pred).mean()), 4),
        "per_class_recall": [round(float(r), 3) for r in
                             recall_score(y_true, y_pred, labels=LABELS, average=None, zero_division=0)],
        "confusion": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        "n": int(len(y_true)),
    }
