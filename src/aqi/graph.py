"""Orchestrator: the pipeline as a LangGraph state machine.

ingestion → profiler → eda → cleaner → features → leakage_guard ─(halt)→ END
                                                        └→ splitter → trainer ⇄ evaluator → critic
                                                                                          └→ tester → explainer → reporter → END
Each node is wrapped so its start, end, duration and any error land in the ledger.
"""
from __future__ import annotations

import time
import traceback

from langgraph.graph import END, StateGraph

from .agents import (cleaner, critic, eda, evaluator, explainer, features, ingestion, leakage_guard,
                     profiler, reporter, splitter, tester, trainer)
from .ledger import Ledger
from .state import PipelineState

NODES = [("ingestion", ingestion), ("profiler", profiler), ("eda", eda), ("cleaner", cleaner),
         ("features", features), ("leakage_guard", leakage_guard), ("splitter", splitter),
         ("trainer", trainer), ("evaluator", evaluator), ("critic", critic), ("tester", tester),
         ("explainer", explainer), ("reporter", reporter)]


def _wrap(name, module, ledger: Ledger):
    def node(state: PipelineState) -> dict:
        ledger.log(name, "start")
        t0 = time.time()
        try:
            update = module.run(state, ledger) or {}
        except Exception as e:
            ledger.log(name, "error", f"{type(e).__name__}: {e}", traceback=traceback.format_exc())
            raise
        ledger.log(name, "halted" if update.get("halted") else "done", seconds=round(time.time() - t0, 1))
        return update
    return node


def build(ledger: Ledger):
    g = StateGraph(PipelineState)
    for name, module in NODES:
        g.add_node(name, _wrap(name, module, ledger))
    g.set_entry_point("ingestion")
    for a, b in [("ingestion", "profiler"), ("profiler", "eda"), ("eda", "cleaner"), ("cleaner", "features"),
                 ("features", "leakage_guard"), ("splitter", "trainer"), ("trainer", "evaluator"),
                 ("evaluator", "critic"), ("explainer", "reporter"), ("reporter", END)]:
        g.add_edge(a, b)
    g.add_conditional_edges("leakage_guard", lambda s: END if s.get("halted") else "splitter")
    g.add_conditional_edges("critic", critic.route)
    g.add_conditional_edges("tester", lambda s: END if s.get("halted") else "explainer")
    return g.compile()


def run(config: dict, run_id: str | None = None) -> tuple[dict, Ledger]:
    ledger = Ledger(run_id)
    ledger.log("pipeline", "start", f"config {config['_path']} (sha {config['_sha']})")
    app = build(ledger)
    final = app.invoke({"run_id": ledger.run_id, "config": config, "paths": {}, "history": [], "iteration": 0},
                       {"recursion_limit": 100})
    ledger.log("pipeline", "halted" if final.get("halted") else "done", final.get("halted", ""))
    return final, ledger
