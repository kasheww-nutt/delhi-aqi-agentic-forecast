"""Shared state passed between graph nodes.

Large tables never live in the state: nodes write parquet files into the run directory and pass
paths. That keeps the state small, serialisable and easy to show in the frontend.
"""
from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    run_id: str
    config: dict
    paths: dict[str, str]            # name → parquet/csv path inside runs/<run_id>/
    stations: list[str]
    feature_groups: dict[str, bool]  # what the critic is allowed to toggle
    feature_columns: list[str]
    trainer_overrides: dict[str, Any]
    iteration: int
    history: list[dict]              # one entry per training iteration (val metrics + action)
    best: dict[str, Any]             # best model so far on validation
    critic_decision: dict[str, Any]
    test_hash: str
    test_results: dict[str, Any]
    halted: str                      # set when a guard stops the run
