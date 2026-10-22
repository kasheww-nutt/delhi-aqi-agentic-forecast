# Delhi Next-Day AQI Forecasting — Agentic ML Pipeline

AUCML (TE7483) ESE case-study project.

**Problem.** Air-quality advisories in Delhi rely on physics-based forecasts (SAFAR, CAMS) that are biased at
street-level stations, while most public ML "AQI predictors" quietly use same-day pollutant readings and so
forecast nothing. This project builds a **leakage-free, next-day AQI-category forecaster** for Delhi's CPCB
stations (2018–2025), fusing station history, on-site meteorology, ERA5 boundary-layer height and the CAMS
day-ahead forecast, and tests whether a lightweight ML layer beats both persistence and the raw physics forecast.

See [`docs/`](docs/) for the project audit and the day-1 data-gate results.

## Pipeline

```
ingestion → profiler → eda → cleaner → features → leakage_guard ─(leak)→ HALT
                                                       └→ splitter (test locked + hashed)
                                                           → trainer ⇄ evaluator → critic ─(STOP)→ tester → explainer → reporter
```

| Agent | Type | Job |
|---|---|---|
| ingestion | rule | station-year CSVs → hourly panel |
| profiler | rule | coverage per station-year; keeps stations with enough PM2.5 data |
| eda | rule + LLM | plots; LLM narrates summary statistics only |
| cleaner | rule | negatives, instrument ceiling, short-gap interpolation, CPCB daily AQI, train-only imputation |
| features | rule | every feature registered with its time offset relative to the issue day |
| leakage_guard | rule | halts the run on unregistered, future or suspiciously target-like inputs |
| splitter | rule (locked) | train 2018–22 / val 2023–24 / test 2025; test file hashed and hidden |
| trainer | tools | persistence, logistic regression, random forest, LightGBM (Optuna on an inner hold-out) |
| evaluator | rule | macro-F1, severe-day recall, ±1-category accuracy on validation only |
| critic | LLM / rule | one whitelisted action per iteration, or STOP; stopping rules enforced in code |
| tester | rule (once) | verifies the hash, refits on train+val, scores 2025 once |
| explainer | rule + LLM | SHAP drivers + plain-language notes |
| reporter | rule | results tables for the report |

Every step is written to `runs/<run_id>/ledger.jsonl`; the dashboard reads only that file.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows; use .venv/bin/pip on macOS/Linux
.venv/Scripts/pip install -e .
```

Data (not committed):

```bash
kaggle datasets download yug201/delhi-air-quality-cpcb-hourly-2010-2026 -p data/raw/delhi_cpcb --unzip
python scripts/fetch_era5_blh.py                  # ERA5 boundary-layer height (no key)
python scripts/fetch_cams.py --start 2018-01 --end 2025-12   # CAMS forecasts, needs ~/.cdsapirc (~2.5 h)
```

The LLM-assisted agents use Claude through the Anthropic SDK (`ANTHROPIC_API_KEY`). Without credentials they
fall back to rule-based behaviour, and the ledger records which path ran.

## Run

```bash
python scripts/run_pipeline.py                 # full run
python scripts/run_pipeline.py --leaky-demo    # adds tomorrow's PM2.5 as a feature: the guard must halt
python scripts/run_pipeline.py --no-llm        # rule-based critic only
streamlit run app/streamlit_app.py             # live dashboard (can also start runs)
pytest                                         # unit tests
```

Set `AQI_REPLAY_FROM=<run_id>` to replay a previous run's cached LLM decisions exactly.
