"""Reporter (rule-based): turns the ledger into a results summary.

It drafts tables and facts only; the written report itself is authored by the team.
"""
from __future__ import annotations

from ..ledger import Ledger

CATS = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


def run(state: dict, ledger: Ledger) -> dict:
    lines = [f"# Run {ledger.run_id} — results summary", ""]
    lines += ["## Training loop (validation 2023–2024)", "",
              "| Iter | Best model | Val macro-F1 | Persistence | Critic action |", "|---|---|---|---|---|"]
    for e in state["history"]:
        lines.append(f"| {e['iteration']} | {e['best_model']} | {e['best_score']:.3f} | "
                     f"{e['scores']['persistence']['macro_f1']:.3f} | {e.get('action', '')} |")
    best = state["best"]
    lines += ["", f"Selected: **{best['model']}** from iteration {best['iteration']} "
              f"(groups: {[g for g, on in best['feature_groups'].items() if on]}).", ""]

    lines += ["## Locked test (2025) — evaluated once", "", "| Model | Macro-F1 | Severe recall | Accuracy | "
              "Within ±1 category |", "|---|---|---|---|---|"]
    for name, m in state["test_results"].items():
        lines.append(f"| {name} | {m['macro_f1']:.3f} | {m['severe_recall']:.3f} | {m['accuracy']:.3f} | "
                     f"{m['within_one_category']:.3f} |")
    cm = state["test_results"][best["model"]]["confusion"]
    lines += ["", f"Confusion matrix ({best['model']}, rows = actual, columns = predicted):", "",
              "| | " + " | ".join(CATS) + " |", "|---" * (len(CATS) + 1) + "|"]
    lines += [f"| **{c}** | " + " | ".join(str(v) for v in row) + " |" for c, row in zip(CATS, cm)]
    lines.append("")

    path = ledger.artifact("results_summary.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    ledger.log("reporter", "info", "results summary written", artifacts=["results_summary.md"])
    return {}
