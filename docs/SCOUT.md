# Source scout (v1.1)

The source scout answers a different question from the forecaster: **"what is probably polluting this
station right now?"** It writes a short brief, with a source for every claim, from live satellite fire data,
mapped pollution sources, the station's latest readings and this week's news.

It is **for explanation and live use only. It never feeds the forecasting model.** Web pages and maps describe
the present, so using them as features for past dates would leak hindsight. The forecaster's numbers in
[RESULTS.md](RESULTS.md) are unchanged by v1.1.

## 1. How a scout runs

1. On the console's **Source scout** page, pick a station and click **Run scout**
   (or run `python -m aqi.scout Anand Vihar` from `src/`).
2. `POST /api/scout` starts `aqi.scout` as a separate process with its own run id (`runs/scout-<time>/`).
3. The scout calls the **Claude Code CLI** with:
   - instructions: explain the pollution, use the tools, never invent a source, under 250 words;
   - our **MCP server** `aqi-scout` ([`scripts/scout_mcp.py`](../scripts/scout_mcp.py)), which the CLI starts itself;
   - permission to use **WebSearch** and **WebFetch**.
4. Claude decides which tools to call and in what order. Each tool returns JSON; a failed tool returns
   `{"error": ...}` instead of crashing, and Claude reports the gap honestly.
5. Claude writes the brief: a one-line answer, then *Recent air quality*, *Likely drivers* (with evidence),
   *What would help* and *Sources*.
6. Each tool call appears in the page's terminal the moment it starts. Every step goes into the run's ledger: the exact CLI command, **each tool call with its input and result**,
   the prompt, the reply and the timing. The page polls every 3 seconds and shows the live terminal and the brief.

## 2. The tools

| Tool | What it returns | Source | Key / limits |
|---|---|---|---|
| `station_snapshot(station, days)` | the station's latest daily AQI, category and PM2.5 | the newest pipeline run's `daily.parquet` | none |
| `fires(start_date, days, region)` | satellite fire count, high-confidence count, count per day, total fire radiative power, the 5 strongest fires | NASA FIRMS, VIIRS (near-real-time for the last 60 days, archive before) | `FIRMS_MAP_KEY` in `.env`; up to 10 days; regions `punjab_haryana`, `delhi_ncr` |
| `nearby_sources(place, radius_km)` | construction sites, industrial areas, landfills, power plants and major roads within 0.5–5 km, nearest first | OpenStreetMap (Nominatim to find the place, Overpass for features) | no key; 3 Overpass mirrors, 25 s each; answers cached in `data/cache/`; when all are busy, a **saved snapshot** for the station is returned, marked with its date |
| WebSearch / WebFetch | this week's news (GRAP stage, waste fires, traffic) and **local sources found by searching the station's locality**: construction or demolition, metro and road works, industrial areas, depots | built into Claude Code | none |

The tool code is in [`src/aqi/scout_tools.py`](../src/aqi/scout_tools.py); the MCP server only wraps it.

## 3. Safety: the CLI gets these tools and nothing else

A Claude Code CLI normally also has file tools, a shell and any accounts the user has connected (for example
Google Drive). Every Claude call in this project is locked down with:

- `--tools <list>`: the only built-in tools available. Empty for the pipeline's agents; `WebSearch,WebFetch`
  for the scout.
- `--strict-mcp-config`: ignore every MCP server and connected account except the ones we pass.
- `--mcp-config <file>`: only our `aqi-scout` server, and only for the scout.
- `--allowedTools`: pre-approve exactly those tools.
- An empty temporary working folder, and a 7-minute limit for the whole scout call.

The CLI's start-up event confirms it: the scout sees exactly `WebFetch`, `WebSearch` and the three
`mcp__aqi-scout__*` tools.

## 4. What is logged

Each scout run's `ledger.jsonl` holds `start`, one `llm` event (command, prompt, reply, `tools` = every tool
call with its input, success and the first 400 characters of its result), then the brief and `done`, or
`error` with the reason. The **Source scout** page shows these as a terminal next to the brief.

## 5. Example

Anand Vihar, 26 Oct 2026, about 3 minutes:

- **Fires:** 618 satellite fire detections in Punjab–Haryana over 22–26 Oct, rising from 67 to 110 a day.
- **News:** GRAP Stage I in force from 21 Oct; news estimates put crop burning at 8–13% of Delhi's pollution.
- **Honesty:** it said the station data ends on 31 Dec 2025, and that the map lookup had failed because
  OpenStreetMap was busy, instead of guessing.

### Example 2: local sources found by web search (27 Oct 2026, 1 min 46 s)

The map servers were busy, so `nearby_sources` failed once and was not retried. A web search of the locality
found the local drivers instead, each with a news link: bus congestion and unauthorised bus parking at the
Anand Vihar ISBT, unpaved roads and potholes, dumped construction waste, open waste burning, and unfinished
DTIDC road works.

## 6. Known limits

- It isn't scored: there is no metric for whether a brief is right. Check its claims against the cited sources.
- OpenStreetMap's public servers are often busy. The scout then relies on its web search of the station's
  locality for local sources (it always runs one). An optional saved snapshot can also be used
  (`src/aqi/osm_snapshot.json`, built with `python scripts/build_osm_snapshot.py`), which the brief marks with its date.
- Mapped sites are not a live permit list: a construction area on the map may be finished.
- Only the Claude Code CLI is wired to the MCP tools. Codex, Gemini CLI and agy also support MCP; connecting
  them is future work.
- The station data comes from the latest pipeline run, which ends in December 2025.

## 7. Files

| File | Role |
|---|---|
| `src/aqi/scout_tools.py` | the tool functions (FIRMS, OpenStreetMap, station data) |
| `scripts/scout_mcp.py` | the MCP server exposing them |
| `src/aqi/scout.py` | the scout agent: instructions, CLI call, logging |
| `src/aqi/llm.py` | CLI calls, tool lock-down, tool-call logging |
| `api/server.py` | `GET /api/scout/stations`, `GET /api/scout`, `POST /api/scout` |
| `web/src/views/ScoutView.tsx` | the console page |
| `scripts/build_osm_snapshot.py` | saves the map lookup for every station, for busy days |
| `src/aqi/osm_snapshot.json` | the saved map lookups (2 km, with the date taken) |
| `tests/test_scout.py` | 8 tests with fake network calls |
