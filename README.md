# Delhi Next-Day AQI Forecasting — Agentic ML Pipeline

AUCML (TE7483) ESE case-study project.

**Problem.** Air-quality advisories in Delhi rely on physics-based forecasts (SAFAR, CAMS) that are biased at
street-level stations, while most public ML "AQI predictors" quietly use same-day pollutant readings and so
forecast nothing. This project builds a **leakage-free, next-day AQI-category forecaster** for 33 CPCB stations
in Delhi (2018–2025), fusing station history, on-site meteorology, ERA5 boundary-layer height and the CAMS
day-ahead forecast, and tests whether a lightweight ML layer beats both persistence and the raw physics forecast.

The pipeline is run by a set of agents (rule-based where correctness matters, LLM where judgement helps),
orchestrated as a state graph, with a locked test set and an experiment ledger so every run is reproducible.

See [`docs/`](docs/) for the project audit and the day-1 data-gate results.
