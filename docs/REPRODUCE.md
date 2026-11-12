# Reproduce the results

Tested on Windows 11 with Python 3.12 and Node 20. The same steps work on macOS/Linux (use `.venv/bin/`
instead of `.venv/Scripts/`).

## 1. Install

```bash
git clone https://github.com/kasheww-nutt/delhi-aqi-agentic-forecast.git
cd delhi-aqi-agentic-forecast
python -m venv .venv
.venv/Scripts/pip install -r requirements-lock.txt   # exact versions; requirements.txt also works
.venv/Scripts/pip install -e .
.venv/Scripts/python -m pytest          # 27 tests should pass
```

`main` includes the dataset (see §3), so the steps below run as they are. The first tagged release
has 18 tests and no data folder: download the data as in §3, or copy `data/` from `main`. The numbers are the same.

## 2. Accounts and keys (never commit these)

| What | Needed for | Where it goes |
|---|---|---|
| Kaggle account + API token | only to re-download the station data | `~/.kaggle/` (see Kaggle's API docs) |
| Copernicus ADS account + API key, CAMS licence accepted | only to re-download the CAMS forecasts | `~/.cdsapirc` |
| A logged-in coding-agent CLI (Claude Code, Gemini CLI, Codex or agy) | optional LLM notes and LLM critic | the CLI's own login |

Without any CLI, run with `--no-llm`: the results are the same (see RESULTS.md §7).

## 3. The data

The files the pipeline reads are already in `data/` (CPCB 2018–2025, `data/raw/cams/cams_daily_delhi.csv`,
`data/raw/era5_delhi_blh.csv`, and the adapted second dataset in `data/processed/vopani_delhi/`). Skip this
section unless you want to download them again or refresh them:

```bash
.venv/Scripts/pip install kaggle                              # the Kaggle command-line tool
kaggle datasets download yug201/delhi-air-quality-cpcb-hourly-2010-2026 -p data/raw/delhi_cpcb --unzip
python scripts/fetch_era5_blh.py                              # about 1 minute, no key
python scripts/fetch_cams.py --start 2018-01 --end 2025-12    # about 2.5 hours; resumes if stopped
python scripts/cams_progress.py                               # optional: live progress bar in another terminal
```

## 4. Run the pipeline

```bash
python scripts/run_pipeline.py --run-id cams-full             # full run, about 6–8 minutes
python scripts/run_pipeline.py --run-id nollm --no-llm        # rule-based critic only
python scripts/run_pipeline.py --run-id leaky --leaky-demo    # the Leakage Guard must halt this run
python scripts/watch_run.py cams-full                         # optional: follow a run live in the terminal
```

Outputs go to `runs/<run-id>/`: `ledger.jsonl` (every decision), `artifacts/` (plots, SHAP, summary, models),
and `locked/test.parquet` (the hashed test year).

**Expected:** split 58,920 / 24,161 / 12,200 rows, test hash starting `b9d3dbfdcb06`, and on the test year
LightGBM macro-F1 0.600 vs persistence 0.583.

**Ablation without CAMS:** set `cams_forecast: false` under `features.groups` in `configs/delhi.yaml` (or
leave `data/raw/cams` empty) and run again. Expected test macro-F1 0.574.

**Replay a run exactly** (LLM answers come from that run's cache, no CLI is called):

```bash
AQI_REPLAY_FROM=cams-full python scripts/run_pipeline.py --run-id cams-replay
```

## 5. Second dataset

The adapted dataset is included, so this runs as it is:

```bash
python scripts/run_pipeline.py --config configs/vopani_delhi.yaml
```

To rebuild it from the raw Kaggle files (220 MB, not in the repository):

```bash
# put the Kaggle "Air Quality Data in India" files in data/raw/external/vopani/
python scripts/adapt_dataset.py data/raw/external/vopani --name vopani_delhi --city Delhi
python scripts/run_pipeline.py --config configs/vopani_delhi.yaml
```

## 6. Console

```bash
cd web && npm install && npm run build && cd ..
uvicorn api.server:app --port 8000          # open http://localhost:8000
```

For development, run `npm run dev` in `web/` (port 5173, proxies `/api` to port 8000).

## 7. Timings on a laptop

| Step | Time |
|---|---|
| Ingestion → leakage guard | about 1.5 min |
| Training + evaluation, per round | about 2 min |
| Tester (refit on train+val, score 2025) | about 2 min |
| Whole run | about 6–8 min (LLM calls add up to a minute) |
| CAMS download, 2018–2025 | about 2.5 hours, one time only |
