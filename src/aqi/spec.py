"""Pipeline layout, kept free of heavy imports so the dashboard can load it instantly."""

NODES = ["ingestion", "profiler", "eda", "cleaner", "features", "leakage_guard", "splitter",
         "trainer", "evaluator", "critic", "tester", "explainer", "reporter"]

KIND = {"ingestion": "rule", "profiler": "rule", "eda": "rule + LLM", "cleaner": "rule", "features": "rule",
        "leakage_guard": "rule", "splitter": "rule (locked)", "trainer": "tools", "evaluator": "rule",
        "critic": "LLM / rule", "tester": "rule (once)", "explainer": "rule + LLM", "reporter": "rule"}
