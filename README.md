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

Every step is written to `runs/<run_id>/ledger.jsonl`; the console reads only that file and the run's artifacts.

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
pytest                                         # unit tests
```

## Bring your own dataset

The pipeline runs on any air-quality dataset that fits the use case. The **schema adapter** agent maps it onto
the canonical schema the Delhi dataset uses ([`src/aqi/schema.py`](src/aqi/schema.py): one row per station-hour,
IST timestamps, 18 pollutant and weather variables in fixed units).

- **Layouts:** wide (one column per variable) or long (OpenAQ-style `parameter / value / unit` rows); CSV, CSV.GZ,
  Parquet or Excel; one file or a folder (side tables with station names and cities are joined automatically).
- **Detection:** timestamp column (or date + time), timezone (tz-aware data is converted to IST), station column
  (or the file name), granularity (sub-hourly is averaged to hours; daily data stays daily).
- **Mapping:** aliases (`O3` → `Ozone`, `pm2_5` → `PM2.5`, …), units from headers or unit columns, converted with
  molar masses for ppb/ppm and standard factors for weather units. Columns the rules can't place are offered to
  Claude, whose answer must name a canonical variable and a convertible unit. A source's own AQI is never imported.
- **Checks:** physically impossible values become missing; data without at least three pollutants (PM2.5 or PM10
  among them) is rejected with a reason.

```bash
python scripts/adapt_dataset.py data/raw/external/vopani --name vopani_delhi --city Delhi
python scripts/run_pipeline.py --config configs/vopani_delhi.yaml
```

The script writes `data/processed/<name>/canonical.parquet`, a `schema_report.json` with every mapping decision,
and `configs/<name>.yaml` with years and a train/val/test split fitted to that dataset. Adapted datasets also appear
in the console's dataset picker. Setting `data.source: {format: auto, path: ...}` in a config adapts inside the run.

## Console (React + FastAPI)

The pipeline console is a React/TypeScript app (`web/`) backed by a small FastAPI service (`api/`). It shows the
agents live, the cleaner's decisions, the critic loop, the locked 2025 test (day-by-day forecast strip per station,
confusion matrix), SHAP drivers and the results summary, and it can start new runs.

```bash
uvicorn api.server:app --port 8000             # API
cd web && npm install && npm run dev           # dev server on http://localhost:5173 (proxies /api)
```

For a single-process setup, run `npm run build` in `web/`, then start uvicorn: it serves the built app at
http://localhost:8000.

Set `AQI_REPLAY_FROM=<run_id>` to replay a previous run's cached LLM decisions exactly.
