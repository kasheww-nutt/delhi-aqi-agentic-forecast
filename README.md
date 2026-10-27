# Delhi Next-Day AQI Forecasting: an Agentic ML Pipeline

AUCML (TE7483) ESE case study · **release v1.0** (the version presented in the deck and report)

**Question.** Can a model beat "tomorrow = today" at forecasting tomorrow's CPCB air-quality category, using
only what is known today?

**Answer.** Yes, narrowly. On the locked 2025 test year (34 Delhi stations, 12,200 station-days, scored once),
LightGBM with the CAMS physics forecast reaches **macro-F1 0.600 vs 0.583** for persistence. It catches **86%
of Very Poor/Severe days** (persistence 84%) and is **within one category on 98% of days**. Without the CAMS
forecast, the same model falls just short of persistence (0.574).

## Why this project is different

- **Truly next-day and leakage-free.** Every feature is registered with its day offset, and a Leakage Guard
  agent halts the run if any input could contain the future. Much public AQI work predicts today's AQI from
  today's pollutants, which forecasts nothing.
- **An honest test.** Time-ordered split (train 2018–22, validation 2023–24, test 2025). The test year is
  hashed and read once, and persistence is in every comparison.
- **ML on top of a physics forecast.** The CAMS global forecast is used as a feature, and the model corrects its
  street-level bias using today's station readings.
- **Categories that matter.** The model predicts the six CPCB categories used for advisories, and Very
  Poor/Severe recall is reported separately.
- **Agents with guardrails.** 14 agents in a fixed LangGraph graph. Rules do everything that must be correct;
  an LLM is used only for notes, mapping unknown columns, and a critic that picks from a whitelist. With no
  LLM at all, the result is identical.
- **Auditable and reusable.** Every decision is written to a ledger, and a schema adapter runs the same
  pipeline on other datasets.

## Documentation

| Document | What it covers |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | task, AQI calculation, cleaning, features, leakage guard, split, models, critic loop, metrics |
| [docs/DATA.md](docs/DATA.md) | data sources, variables, the CAMS leakage-safe setup, data quality, the second dataset |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the 14 agents, state, ledger, LLM CLIs, API and console, repository layout |
| [docs/RESULTS.md](docs/RESULTS.md) | every result with its source run, plus honest limits |
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | install, keys, downloads, commands, expected numbers, timings |
| [docs/VIVA_PREP.md](docs/VIVA_PREP.md) | viva guide in simple words: story, choices, likely questions |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | every term used, explained simply with a project example |
| [docs/results/](docs/results/) | the saved run ledgers, figures and `results.json` behind every number |
| [docs/planning/](docs/planning/) | the original project audit and day-1 data-gate notes |

## Pipeline

```
schema_adapter → ingestion → profiler → eda → cleaner → features → leakage_guard ─(leak)→ HALT
                                                                       └→ splitter (test locked + hashed)
                     trainer ⇄ evaluator → critic ─(STOP)→ tester → explainer → reporter
```

| Agent | Type | Job |
|---|---|---|
| schema_adapter | rule + LLM | maps any suitable dataset onto the canonical schema |
| ingestion | rule | station-year CSVs → hourly panel |
| profiler | rule | coverage per station-year; keeps stations with enough PM2.5 data |
| eda | rule + LLM | plots; the LLM narrates summary statistics only |
| cleaner | rule | negatives, instrument ceiling, short-gap interpolation, CPCB daily AQI, train-only imputation |
| features | rule | 45 features, each registered with its offset from the issue day |
| leakage_guard | rule | halts the run on unregistered, future or suspiciously target-like inputs |
| splitter | rule (locked) | train 2018–22 / val 2023–24 / test 2025; test file hashed and hidden |
| trainer | tools | persistence, logistic regression, random forest, LightGBM (Optuna on an inner hold-out) |
| evaluator | rule | macro-F1, Very Poor/Severe recall and more, on validation only |
| critic | LLM / rule | one whitelisted action per round, or STOP; stopping rules enforced in code |
| tester | rule (once) | verifies the hash, refits on train+val, scores 2025 once |
| explainer | rule + LLM | SHAP drivers + plain-language notes |
| reporter | rule | results tables for the report |

## Quick start

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt && .venv/Scripts/pip install -e .
python -m pytest                                   # 18 tests
python scripts/run_pipeline.py --no-llm            # needs the data: see docs/REPRODUCE.md
uvicorn api.server:app --port 8000                 # console at http://localhost:8000 (after npm run build in web/)
```

The LLM agents use coding-agent CLIs that are already logged in (Claude Code, Gemini CLI, Codex, agy), run
headless, so there is no API bill. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), section 4.

## Stack

Python 3.12 · pandas · scikit-learn · LightGBM · Optuna · SHAP · LangGraph · FastAPI · React + TypeScript (Vite)

## Data credits

Delhi CPCB station data (Kaggle `yug201`), ERA5 via Open-Meteo, CAMS global forecasts from the Copernicus
Atmosphere Data Store (CC-BY 4.0), and Kaggle "Air Quality Data in India (2015–2020)". Raw data is not
redistributed here; [docs/DATA.md](docs/DATA.md) explains how to download it.
