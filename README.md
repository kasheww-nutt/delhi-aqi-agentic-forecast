# Delhi Next-Day AQI Forecasting: an Agentic ML Pipeline

AUCML (TE7483) ESE case study · **v1.1** = v1.0 (the version in the deck and report, tag `v1.0-ese`) + the source scout

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
| [docs/SCOUT.md](docs/SCOUT.md) | v1.1 source scout: live explanation of what is polluting a station (MCP tools + web search) |
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

## Dataset (included)

The data the pipeline reads is in the repository, so a clone runs straight away with no accounts or downloads
(about 150 MB to clone, 340 MB on disk).

| Folder / file | What | Size |
|---|---|---|
| `data/raw/delhi_cpcb/2018/` … `2025/` | CPCB hourly readings, one CSV per station per year: 36 stations × 8 years = 288 files, ~2.52 million hourly rows, 18 variables | 322 MB |
| `data/raw/cams/cams_daily_delhi.csv` | CAMS forecast of tomorrow's PM2.5 (mean, max), one row per issue day, 2018–2025 | 91 KB |
| `data/raw/era5_delhi_blh.csv` | ERA5 boundary-layer height for central Delhi, one row per day | 88 KB |
| `data/processed/vopani_delhi/` | the second dataset (Kaggle "Air Quality Data in India", Delhi 2015–2020) already adapted to our schema | 19 MB |

Where it comes from and what each column means: [docs/DATA.md](docs/DATA.md) and
[`data/raw/delhi_cpcb/README.md`](data/raw/delhi_cpcb/README.md). Only the raw Vopani file (220 MB, over
GitHub's file limit) and the raw CAMS downloads are left out; [docs/REPRODUCE.md](docs/REPRODUCE.md) shows how to
fetch them again.

**Using your own dataset.** Any air-quality data can be used if it has a time column, a station column, and at
least 3 pollutants including PM2.5 or PM10, over at least 3 years. The console's **Data** page lists exactly
what is accepted: the 18 variables, their units and the units converted automatically, plausible ranges and the
column names recognised. Then run:

```bash
.venv/Scripts/python scripts/adapt_dataset.py path/to/your/folder --name mydata --city Delhi
.venv/Scripts/python scripts/run_pipeline.py --no-llm --config configs/mydata.yaml
```

## How to run it

You need **Python 3.12** and **git**. **Node 20** is needed only for the web console. Commands are for
Windows (Git Bash or PowerShell); on macOS/Linux use `.venv/bin/` instead of `.venv/Scripts/`.

**1. Get the code and install (about 3 minutes)**

```bash
git clone https://github.com/kasheww-nutt/delhi-aqi-agentic-forecast.git
cd delhi-aqi-agentic-forecast
python -m venv .venv
.venv/Scripts/pip install -r requirements-lock.txt
.venv/Scripts/pip install -e .
```

`requirements-lock.txt` pins the exact versions the results were produced with. `requirements.txt` (minimum
versions) also works and gives the same scores. The only difference is the test file's hash, because pandas
writes its own version into the file.

On Windows, if pip stops with *"No such file or directory … Long Path support"*, clone into a short folder (for
example `C:\aqi`) and install again. One package has very long file names.

**2. Check everything works (under a minute)**

```bash
.venv/Scripts/python -m pytest
```

All 27 tests should pass.

**3. Run the whole pipeline (about 6–8 minutes)**

```bash
.venv/Scripts/python scripts/run_pipeline.py --no-llm --run-id my-run
```

- `--no-llm` uses the rule-based critic and needs nothing else installed. The result is identical to the
  LLM run.
- To use the LLM agents, drop `--no-llm`. They call coding-agent CLIs that are already logged in on your
  machine (Claude Code, Gemini CLI, Codex or agy), so there is no API bill. If none answers, the rules take over.
- **What you should see:** the split is 58,920 / 24,161 / 12,200 rows, the test hash starts `b9d3dbfdcb06`, and
  on the 2025 test year LightGBM scores **macro-F1 0.600 vs 0.583** for persistence.
- **Outputs** go to `runs/my-run/`:
  - `ledger.jsonl`: every decision;
  - `artifacts/results_summary.md`: the results tables;
  - `artifacts/`: plots and SHAP.

**4. Other runs (optional)**

```bash
.venv/Scripts/python scripts/run_pipeline.py --no-llm --run-id leaky --leaky-demo                 # adds tomorrow's PM2.5: the Leakage Guard must halt
.venv/Scripts/python scripts/run_pipeline.py --no-llm --run-id vopani --config configs/vopani_delhi.yaml   # the second dataset
.venv/Scripts/python scripts/watch_run.py my-run                                                 # follow a run live in another terminal
```

To run without the CAMS forecast, set `cams_forecast: false` under `features.groups` in
[`configs/delhi.yaml`](configs/delhi.yaml). Expected test macro-F1: 0.574.

**5. Open the web console (optional, needs Node)**

```bash
cd web
npm install
npm run build
cd ..
.venv/Scripts/uvicorn api.server:app --port 8000
```

Open http://localhost:8000. It shows every run in `runs/`: each agent's work, cleaning, the leakage check,
training rounds, test results and SHAP. You can also start a new run from there.

The **Source scout** page also needs the Claude Code CLI logged in, and a free NASA FIRMS key in `.env` as
`FIRMS_MAP_KEY=...` (see [docs/SCOUT.md](docs/SCOUT.md)).

More detail, timings and how to re-download the data: [docs/REPRODUCE.md](docs/REPRODUCE.md).

## Source scout (v1.1)

A separate agent explains what is probably polluting a station right now. The Claude Code CLI calls our own MCP
tools (NASA FIRMS crop fires, OpenStreetMap pollution sources, the station's latest readings) plus web search, and
writes a short brief with every claim sourced. It is for explanation only and never feeds the model. Run it from
the console's **Source scout** page. Details: [docs/SCOUT.md](docs/SCOUT.md).

## Stack

Python 3.12 · pandas · scikit-learn · LightGBM · Optuna · SHAP · LangGraph · FastAPI · React + TypeScript (Vite)

## Data credits

Delhi CPCB station data (Kaggle `yug201`), ERA5 via Open-Meteo, CAMS global forecasts from the Copernicus
Atmosphere Data Store (CC-BY 4.0), and Kaggle "Air Quality Data in India (2015–2020)". The station data was
originally published by the Central Pollution Control Board (CPCB), Government of India. The copies in `data/`
are included so the project can be reproduced; [docs/DATA.md](docs/DATA.md) lists each source and its licence.
