# Architecture

## 1. Big picture

```
configs/*.yaml ──► scripts/run_pipeline.py ──► LangGraph state machine (14 agents)
                                                     │  every agent appends to
                                                     ▼
                                     runs/<run_id>/ledger.jsonl  +  artifacts/
                                                     │  read-only
                                                     ▼
                                  api/server.py (FastAPI)  ──►  web/ (React console)
```

- **Config:** one YAML file per dataset. Every setting an agent uses comes from it, and the run logs the
  config's hash, so you always know exactly what ran.
- **Graph:** [`src/aqi/graph.py`](../src/aqi/graph.py) wires the agents into a LangGraph `StateGraph`.
- **State:** a shared dictionary ([`src/aqi/state.py`](../src/aqi/state.py)) holding file paths, the active
  feature groups, the round history and the critic's last decision. Large data lives in Parquet files; the
  state only holds their paths.
- **Ledger:** [`src/aqi/ledger.py`](../src/aqi/ledger.py) appends one JSON line per event (start, info, done,
  halt, error, LLM call). It is the single source of truth: the console and the reporter read only the ledger
  and the artifacts.

## 2. The agent graph

```
schema_adapter → ingestion → profiler → eda → cleaner → features → leakage_guard ─(leak)→ HALT
                                                                       │
                                                                       ▼
                                                                    splitter (test locked + hashed)
                                                                       │
                                     ┌──────── trainer → evaluator → critic ──(STOP)→ tester → explainer → reporter
                                     └───────────── one whitelisted action ◄──┘
```

Each node is wrapped so that its start, end, duration and any error are logged automatically.

## 3. The 14 agents

| # | Agent | Type | Reads | Writes / decides |
|---|---|---|---|---|
| 1 | schema_adapter | rule + LLM | the config's data source | canonical hourly data (skipped for the native Delhi format) |
| 2 | ingestion | rule | station-year CSVs | one hourly panel (station × hour) |
| 3 | profiler | rule | hourly panel | coverage per station-year; which stations to keep; coverage heatmap |
| 4 | eda | rule + LLM | hourly panel | plots, summary stats; LLM notes from stats only |
| 5 | cleaner | rule | hourly panel | daily station panel, observed AQI and category, imputed inputs, decision list |
| 6 | features | rule | daily panel, ERA5, CAMS | 45 features + the feature registry |
| 7 | leakage_guard | rule | features + registry | passes, or **halts the run** |
| 8 | splitter | rule (locked) | features | train/val files; locked, hashed test file |
| 9 | trainer | tools | train file | fitted models (persistence, logistic regression, random forest, LightGBM) |
| 10 | evaluator | rule | validation file | scores for every model, validation only |
| 11 | critic | LLM / rule | validation history | one whitelisted action, or STOP |
| 12 | tester | rule (once) | locked test file | verifies the hash, refits on train+val, scores 2025 once |
| 13 | explainer | rule + LLM | final model | SHAP importance; LLM plain-language notes |
| 14 | reporter | rule | ledger | results summary tables (`results_summary.md`) |

Agents 4, 11 and 13 (and 1 for unknown columns) can use an LLM. All others are pure rules.

## 4. How the LLM agents call an LLM ([`src/aqi/llm.py`](../src/aqi/llm.py))

- **Backend `cli` (default):** the coding-agent CLIs already logged in on the machine, run headless, so there
  is no API bill:
  - Claude Code: `claude -p --output-format json` (prompt on stdin)
  - Gemini CLI: `gemini -p … -o json --approval-mode plan`
  - Codex: `codex exec … -s read-only --output-schema <file>`
  - agy: `agy --output-format json --mode plan --json-schema <file> -p=<prompt>`
- They are tried in the order set in the config. If one fails, times out (240 s) or hits a usage limit, the
  next one is tried.
- Every call runs in an **empty temporary folder** in read-only or plan mode, so a CLI cannot touch the project.
- Claude Code calls are locked down further (v1.1): `--tools` lists the only built-in tools (none for pipeline
  agents), and `--strict-mcp-config` drops every MCP server or connected account except ones we pass. Each tool
  call the CLI makes is logged.
- Answers must match the agent's **JSON schema** and allowed values, or they are rejected.
- Every answer is **cached** by a hash of the prompt in the run folder. `AQI_REPLAY_FROM=<run_id>` replays a
  finished run's decisions exactly, without calling any LLM.
- Every call is logged: which CLI, the exact command, the prompt, the reply, the time taken, any error.
- When no LLM answers (or `--no-llm` is used), every agent falls back to its rule-based behaviour, and the
  ledger records why.
- Backend `api` uses the Anthropic API with an `ANTHROPIC_API_KEY` instead.

## 5. Console

- **API** ([`api/server.py`](../api/server.py)):
  - `GET /api/spec`: the agent list and types.
  - `GET /api/schema`: what data the pipeline accepts (variables, units, ranges, recognised column names), read from `src/aqi/schema.py`; shown at the top of the **Data** page.
  - `GET /api/runs`: all runs with status and headline score.
  - `GET /api/runs/{id}/events`: the run's ledger.
  - `GET /api/runs/{id}/artifacts/{name}`, `/text/{name}`, `/predictions`, `/shap`: outputs.
  - `GET /api/configs`: available datasets.
  - `POST /api/runs`: start a new run.
- **Web app** ([`web/`](../web/), React + TypeScript + Vite): pages for Overview, Agent terminals (each agent's
  live output, including the exact CLI calls), Data, Training loop, Test year, Drivers, Ledger and Summary.
  Each page has a link (`#<run>/<page>`) you can bookmark.

## 6. Repository layout

| Path | What is in it |
|---|---|
| `configs/` | one YAML per dataset (`delhi.yaml`, `vopani_delhi.yaml`) |
| `src/aqi/agents/` | one module per agent, each exposing `run(state, ledger)` |
| `src/aqi/graph.py` | the LangGraph state machine |
| `src/aqi/schema.py` | canonical variables, units, aliases, valid ranges |
| `src/aqi/aqi_index.py` | CPCB AQI breakpoints and categories |
| `src/aqi/metrics.py` | all evaluation metrics |
| `src/aqi/llm.py` | CLI/API access, schemas, caching, replay |
| `src/aqi/ledger.py` | the experiment ledger |
| `scripts/` | run the pipeline, adapt a dataset, download ERA5 and CAMS, watch a run in the terminal |
| `api/`, `web/` | FastAPI service and React console |
| `tests/` | 27 unit tests: AQI, leakage guard, splits, schema adapter, LLM CLI handling, scout tools |
| `src/aqi/scout*.py`, `scripts/scout_mcp.py` | v1.1 source scout and its MCP tool server ([SCOUT.md](SCOUT.md)) |
| `docs/` | these documents, the results snapshot and the planning audits |
