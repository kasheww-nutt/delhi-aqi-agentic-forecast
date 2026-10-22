"""Pipeline agents. Each exposes `run(state, ledger) -> dict` returning a partial state update.

Rule-based: ingestion, profiler, cleaner, features, leakage_guard, splitter, trainer, evaluator, tester.
Rule-based + LLM narration: eda, explainer. LLM with rule-based fallback: critic.
"""
