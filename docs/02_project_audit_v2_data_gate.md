# AUCML ESE Project Audit v2: P1 vs P2 Deep Dive + Agentic Pipeline Design

This document builds on `Project_Audit.md` and covers three questions:
1. Is the P1 dataset good enough? What do current and upcoming research suggest instead?
2. Is the P2 dataset dense and large enough?
3. Does the proposed agentic pipeline hold up, and how should it be built so that it *gains* marks instead of losing them in the viva?

---

## Part A: P1 (Next-day AQI forecasting) dataset audit

> **Update (day-1 data gate, 2026-10-22):** the sources in A3 were tested live, and the plan changed. The core dataset is now **36 Delhi CPCB stations, 2017–2025**, the split is now Train 2017–22 / Val 2023 + H2-2024 / Test 2025, and CAMS needs a Copernicus account. **Part E at the end of this file overrides A3 and A6.**

### A1. What is wrong with the v1 dataset (Kaggle "Air Quality Data in India 2015–2020")

| Issue | Why it matters for the ESE |
|---|---|
| **Ends mid-2020.** The v1 plan's "test = 2020" is *almost entirely COVID lockdown*. | Lockdown is a severe distribution shift. Testing only on it makes every model look bad for the wrong reason. **This was a flaw in v1's split.** |
| **City-level aggregates** (`city_day.csv`): an average of an unknown number of stations, and stations come and go over time. | A city's "PM2.5" level can jump because a station was added, not because the air changed. That is hard to defend in the viva. |
| **No meteorology.** | The literature agrees that wind, temperature inversions and boundary-layer height drive Indian winter pollution episodes ([Sci. Reports 2025](https://www.nature.com/articles/s41598-025-16664-4)). Without weather you are forecasting with one hand tied. |
| **No fire data.** | Stubble burning in Punjab/Haryana dominates Oct–Nov in North India. |
| **Heavily used on Kaggle** (hundreds of notebooks). | Low novelty headroom on its own. |
| **Data is 5+ years old.** | Weak "real-world relevance" for row 1. |

**Verdict:** it is fine for prototyping, but too weak to be the main dataset.

### A2. What existing research does, and the gap we can use

| Work | What it does | Gap we exploit |
|---|---|---|
| [arXiv 2404.08702](https://arxiv.org/pdf/2404.08702): AQI across Delhi/Haryana/Punjab, 22 CPCB stations, CatBoost/XGB/RF/SVR/SARIMAX/LSTM | Predicts AQI *from pollutant concentrations*. The abstract does not state a forecast horizon. | This is the "same-day leakage" pattern. Our honest **t+1 forecast** is a direct improvement. |
| [Aerosol Sci. Tech. 2025](https://www.tandfonline.com/doi/full/10.1080/02786826.2025.2513503): ANN/SVR/RF for Delhi PM2.5 during stubble season | Delhi only, one season, regression | We cover multiple cities, the full year and the **category** (which is what advisories use). |
| [Sci. Reports 2025](https://www.nature.com/articles/s41598-025-16664-4): LSTM + attention + transfer learning, 10 Delhi winters, meteorology + fire counts | Heavy deep learning, Delhi only | Shows that **meteorology + fire features matter**. We use them in a lightweight, explainable model. |
| [SAFAR (Env. Modelling & Software 2021)](https://repository.ias.ac.in/133316/): IITM Pune's operational forecast system | A physics model plus **Model Output Statistics (MOS)** correction. Delhi PM2.5 normalised gross error is about 35%. | Operational systems already *correct physics forecasts with statistics*. We can do a student-scale version with ML. |
| CAMS global forecasts (Copernicus), [free via Open-Meteo](https://open-meteo.com/en/docs/air-quality-api) | Global 0.4° (~45 km) forecast, 5 days ahead, available from Aug 2022 | Global models are biased at Indian street-level stations. **An ML bias-correction layer** is a current, defensible novelty. |

### A3. Recommended data stack for P1 (multi-source, all free)

| Layer | Source | What you get | Notes / verify before committing |
|---|---|---|---|
| **Target + pollutant history** | CPCB CAAQMS station data via the [Vayuayan AQI Archive](https://saket-choudhary.me/vayuayan-archive) (560+ stations, MIT licence, gzipped CSV) **or** [OpenAQ v3 API](https://docs.openaq.org/using-the-api/quick-start) (free key) | PM2.5, PM10, NO2, SO2, CO, O3, NH3 per station | ⚠ I could not confirm how far back Vayuayan's history goes. Check this on day 1. For 2015–2019 the [Princeton CPCB hourly archive](https://datacommons.princeton.edu/discovery/catalog/doi-10-34770-60j3-yp02) (CC BY 4.0) is a solid backfill. |
| **Meteorology** | [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (ERA5, from 1940, no key for non-commercial use) | Temperature, RH, wind speed/direction, pressure, precipitation, boundary-layer height | Derived feature: **ventilation index = wind speed × boundary-layer height** (low value = pollution trapped). ⚠ Confirm the PBL variable returns data for your coordinates. |
| **Physics-model forecast** | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) (CAMS global forecast) | CAMS-forecast PM2.5/PM10/AOD for day t+1, issued on day t | Available from **Aug 2022**. ⚠ You must use the forecast *issued on day t*, not reanalysis of day t+1, otherwise you leak the future. Confirm archived-forecast access. |
| **Fire activity** | NASA FIRMS (MODIS/VIIRS active fires, free map key) | Daily fire counts / fire radiative power in Punjab–Haryana boxes | Weight by wind direction: "upwind fire load". |
| **Calendar** | Hand-built | Diwali window, festivals, weekends, lockdown flag | [arXiv 2404.08702](https://arxiv.org/pdf/2404.08702) reports about +40 µg/m³ PM2.5 on Diwali days in 2018. |

**Scope it down so it stays feasible:** about **12–20 stations** in 5–6 cities with contrasting climates (Delhi-NCR, Pune, Mumbai, Kolkata, Bengaluru, Lucknow). Pick stations with at least 70% daily coverage over **2019–2025**. That is roughly 15 stations × 2,400 days ≈ 36k station-days: laptop-scale, but far richer than v1.

### A4. Revised P1 problem statement

> Air-quality advisories in India are issued from physics-based forecasts (SAFAR, CAMS) that are known to be biased at street-level stations, especially in winter. Meanwhile, most public ML "AQI predictors" quietly use same-day pollutant readings and so forecast nothing. **We build a leakage-free, next-day AQI-category forecaster for CPCB stations across six Indian cities. It fuses station history, ERA5 meteorology, upwind crop-fire activity and the CAMS global forecast. We test whether a lightweight ML correction layer beats both persistence and the raw physics forecast, especially on "Very Poor/Severe" days, when advisories matter most.**

### A5. Revised novelty (each item is simple and produces a comparison table)
1. **Leakage audit:** the same-day "naive" model vs the honest t+1 model. One table shows why most online work is inflated.
2. **ML-on-physics (MOS-style) correction:** compare `persistence` vs `raw CAMS` vs `ML without CAMS` vs `ML + CAMS`. This is the headline result.
3. **Episode recall:** report recall and precision for Very Poor + Severe days (the advisory-critical classes), not just overall accuracy.
4. **Generalisation:** leave-one-city-out. Can the model forecast a city it never trained on?
5. **Stress test:** the 2020 lockdown as a separate, labelled shift experiment, *not* as the main test set.

### A6. Revised P1 split (fixes the v1 flaw)
| Set | Period | Used for |
|---|---|---|
| Train | 2019-01 → 2022-12 | Fitting (exclude or flag Mar–Jun 2020) |
| Validation | 2023 | Tuning, critic loop, threshold choice |
| **Test (locked)** | 2024 → latest available | Evaluated **once** at the end |
| Track B (CAMS experiments) | Train Aug 2022 → 2023, test 2024+ | Because CAMS archive starts Aug 2022 |
| LOCO | Rotate held-out city, same time split | Generalisation experiment |

---

## Part B: P2 (Student dropout early warning) dataset audit

### B1. Is the UCI Portalegre dataset dense and big enough?

**Short answer: it is big enough for a basic classifier, but not dense enough for the *early-warning* story we pitched.**

| Check | Finding | Verdict |
|---|---|---|
| Size | 4,424 students × 36 features, 3 classes | ✅ Enough for classical ML with stratified CV |
| Temporal density | Only **two aggregated semester snapshots** (units enrolled, approved, grade per semester) | ❌ "Early warning" can only mean enrolment → sem 1 → sem 2. That is coarse, and by sem 2 it is late. |
| Behavioural signal | None (no attendance, LMS activity or assignment timing) | ❌ The research consensus is that behavioural/temporal features dominate dropout prediction ([survival benchmark, arXiv 2604.08870](https://arxiv.org/pdf/2604.08870)) |
| Label quality | "Enrolled" (~18%) is a *censored* outcome (still studying, final status unknown), not a real class | ⚠ Hard to defend in the viva as a prediction target |
| Macro features | Unemployment, inflation and GDP appear to vary only by enrolment cohort, so they act as a hidden cohort ID | ⚠ Check with `nunique()`. If confirmed, drop them or explain them. |
| Missingness | None | ⚠ Thin material for rubric row 2 |
| Generalisability | One Portuguese polytechnic | ⚠ Limited |
| Saturation | Used for Kaggle Playground S4E6 (2024) | ⚠ Many public notebooks to compete with |

### B2. Better dataset: OULAD (Open University Learning Analytics Dataset)
| Property | Value |
|---|---|
| Size | **32,593 enrolments** (≈28.8k unique students), 7 modules, 4 presentations (2013–2014) |
| Tables | Students/demographics, registration dates, assessments (with submission dates), **daily VLE clickstream (~10M rows)** |
| Target | Pass / Distinction / Fail / Withdrawn (withdrawal ≈ 22.7% of enrolments in survival framing) |
| Why it fits | **True weekly early warning** is possible: features as of day 14, 28, 56 and so on |
| Evidence | A day-28 study reports ROC-AUC 0.79, rising from 0.747 at day 14 to 0.835 at day 56. That trade-off between earliness and accuracy is exactly the curve our project would study. |
| Licence | CC BY 4.0 (Open University) |

**Caveat:** OULAD is well studied in learning-analytics research (survival benchmarks already exist), so P2's novelty would be **operational**, not methodological:
- an "earliest reliable week" chosen under a counsellor-capacity constraint (e.g. "we can contact 10% of students per week"),
- **leave-future-presentation-out** validation (train on 2013 runs, test on 2014J), which matches how a real deployment would work,
- per-module transfer (train on STEM modules, test on social-science modules).

### B3. P2 verdict
- **Stay with UCI** only if you want the smallest, safest project. Reframe it honestly as "enrolment-time + semester-1 risk screening", not a weekly early-warning system.
- **Switch to OULAD** if you want P2 to be competitive with P1. It has denser data, an actual time dimension, and a multi-table join that makes the data-handling row rich.

---

## Part C: P1 vs P2 after the audit

| | P1 (multi-source AQI) | P2 (OULAD dropout) |
|---|---|---|
| Impact / relevance | ★★★★★ (India, live, public health; IITM's SAFAR is from Pune) | ★★★★ |
| Dataset richness (row 2) | ★★★★★ (4 sources, real missingness) | ★★★★ (multi-table, clickstream) |
| Novelty headroom | ★★★★★ (ML correction of CAMS is current and rarely done at student level) | ★★★ (operational framing only) |
| Engineering risk | ★★★ (API pulls, joins, the CAMS archive needs verification) | ★★★★ (static download) |
| Fit with an agentic pipeline | ★★★★★ (each source/stage maps naturally to an agent) | ★★★★ |
| **Recommendation** | **Primary** | **Fallback** (build the agent harness generic so it can switch) |

**Day-1 gate for P1:** within the first 2 days, confirm (a) station history depth on Vayuayan/OpenAQ and (b) CAMS archived-forecast access. If (b) fails, drop novelty item 2 (CAMS correction) and keep the rest; P1 still stands. If (a) fails, fall back to Princeton 2015–2019 + OpenAQ.

---

## Part D: Agentic pipeline audit

### D1. Your idea, assessed

| Your proposal | Assessment |
|---|---|
| Separate EDA / Cleaner / Splitter / Trainer / Evaluator / Critic agents | ✅ Good. It maps one-to-one to rubric rows 2–5 and makes the pipeline *visible*. |
| Some agents rule-based from the dataset schema, some LLM | ✅ The right instinct. Details are in D3. |
| Pipeline visible on a frontend | ✅ Helps rows 4 and 7 a lot. |
| **"If the result is not good, the split will be better and the model will be retrained"** | ❌ **This is the biggest risk in the whole plan.** If the critic can change the split, or sees test scores, the loop *optimises on the test set*. That is data snooping, and any ML examiner will catch it in the viva. The split for P1 is fixed by the problem (time order). It is not a knob to tune. |
| Trainer as a "true agent" that trains models | ⚠ An LLM choosing hyperparameters is worse than Optuna and non-deterministic, which hurts the reproducibility row. Let the LLM decide **what to try next**; let Optuna/sklearn **do** the training. |

### D2. Guardrails that turn the agent loop into a strength
1. **Locked test set.** The Splitter writes the test indices once and stores a hash. No agent can read test labels. A final `Tester` step runs exactly once after the loop ends.
2. **The critic sees validation metrics only** and can only choose from a **whitelist of actions**:
   - widen or narrow a hyperparameter search space
   - toggle class weighting / focal loss / SMOTE (inside folds)
   - add or remove a *pre-registered* feature group (weather, fire, CAMS, lags)
   - switch between *pre-registered* imputation strategies
   - **Forbidden:** changing split dates, dropping hard classes, touching test data, editing metric definitions.
3. **A Leakage Guard agent (rule-based)** checks that every feature column has `source_timestamp ≤ forecast_issue_time`. This is P1's novelty item 1, enforced automatically. It is a great viva demo.
4. **Stopping rule:** at most 5 iterations, *or* stop when validation Macro-F1 improves by less than 0.01, *or* when a compute budget is reached.
5. **An experiment ledger** (MLflow or a JSON log) records every iteration: action, critic rationale, validation metrics. The report then shows the full search honestly. Over-tuning on validation is visible, and you can quantify it (validation vs final test gap).
6. **Reproducibility:** fixed seeds, LLM at temperature 0, and every LLM decision cached in the ledger, so the whole run can be **replayed** without calling the LLM again.

### D3. Agent roster (P1)

| # | Agent | Type | Inputs → outputs | Rubric row |
|---|---|---|---|---|
| 0 | **Orchestrator** | State graph (LangGraph) | Runs nodes, handles retries and the loop | 3, 4 |
| 1 | **Ingestion** | Rule | Pulls CPCB/OpenAQ, Open-Meteo, CAMS, FIRMS → raw parquet; schema validated with `pandera` | 2 |
| 2 | **Profiler** | Rule (schema-driven) | Dtypes, ranges, missingness, per-station coverage → `profile.json`; selects stations with ≥70% coverage | 2 |
| 3 | **EDA** | Rule (plots) + LLM (narration) | Missingness heatmap per station/pollutant, seasonality (Oct–Jan peak), city comparison, fire–PM2.5 lag correlation; the LLM writes observations **from summary stats only** | 2, 7 |
| 4 | **Cleaner** | Rule (config) | Drops pollutants with >60% missing (logged justification), per-station time interpolation for gaps ≤3 days, station-month median for longer gaps, missing-indicator flags, physical-range outlier caps | 2 |
| 5 | **Feature builder** | Rule | Lags t…t−7, rolling 3/7-day stats, ventilation index, upwind fire load, CAMS t+1 forecast, calendar flags | 2, 3 |
| 6 | **Leakage Guard** | Rule | Asserts temporal validity of every feature; blocks the run if violated | 3 (novelty) |
| 7 | **Splitter** | Rule (locked) | Time split + LOCO folds; writes test hash | 2, 3 |
| 8 | **Trainer** | Tool-using agent: LLM picks the next experiment, Optuna executes | B0 Persistence, B1 raw CAMS, M1 multinomial LR, M2 Random Forest, M3 LightGBM/XGBoost, (M4 LSTM, optional) | 3, 4 |
| 9 | **Evaluator** | Rule | Macro-F1, per-class recall (Very Poor/Severe), confusion matrix, ordinal error (how many buckets off), MAE on AQI value, calibration | 5 |
| 10 | **Critic** | LLM + rubric prompt | Reads validation metrics + error slices (by city, season, class) → diagnosis + one whitelisted action, or STOP | 3, 5 |
| 11 | **Tester** | Rule | Runs once on the locked test set, plus LOCO and lockdown stress tests | 5 |
| 12 | **Explainer** | Rule (SHAP) + LLM narration | Global and per-city drivers; "why tomorrow is Severe" | 5, 8 |
| 13 | **Reporter** | LLM | Drafts report sections from the ledger (a human edits the final version) | 6 |

**Rule-based vs LLM split:** anything that must be *correct and repeatable* (cleaning, splitting, metrics, leakage checks) is rule-based. The LLM is used only where *judgement or language* adds value: narration, diagnosis, choosing the next experiment, report drafting. This is easy to defend in the viva.

### D4. Flow

```
            ┌──────────────┐
            │ Orchestrator │  (LangGraph state machine; every node streams status to UI)
            └──────┬───────┘
Ingestion → Profiler → EDA → Cleaner → Feature builder → Leakage Guard ─✗→ halt + report
                                                              │✓
                                                         Splitter (writes locked test hash)
                                                              │
                                   ┌──────────────────────────▼──────────────────────┐
                                   │  Trainer ──► Evaluator (VALIDATION only) ──► Critic │
                                   │     ▲                                          │   │
                                   │     └──── whitelisted action ◄─────────────────┘   │
                                   │  stop: 5 iters | ΔMacro-F1 < 0.01 | budget          │
                                   └──────────────────────────┬──────────────────────┘
                                                              │
                                     Tester (ONE run: test + LOCO + lockdown stress)
                                                              │
                                                 Explainer → Reporter → Dashboard
```

### D5. Tech stack (4–5 week student scale)
| Layer | Choice | Why |
|---|---|---|
| Orchestration | **LangGraph** | Explicit state graph, loops with conditions, easy to visualise |
| ML | scikit-learn, LightGBM/XGBoost, Optuna, SHAP | Standard and defensible |
| Data validation | pandera | Gives the schema-driven agents a contract |
| Tracking | MLflow (local) or a JSON ledger | The experiment ledger |
| LLM | Any API model (e.g. Claude Sonnet) or a local model via Ollama for zero cost | Only 4 agents use it, so the cost is small |
| Backend | FastAPI + Server-Sent Events | Streams node status to the UI |
| Frontend | **Streamlit** (fastest) **or** React + React Flow (best-looking DAG) | Shows the live DAG with node colours, per-node logs/plots, critic rationale per iteration, ledger table, final scorecards, and a "forecast tomorrow" tab |

### D6. Viva framing (important)
- **The ML pipeline is the project. The agent layer is the execution and audit harness.** Never let the agents become the topic; examiners grade the ML.
- Prepare clear answers to:
  - "Why can't the critic change the split?" (data snooping; time order is part of the problem definition)
  - "Isn't the critic overfitting validation?" (yes, a little; that is why there is a locked test set and an iteration cap, and the validation–test gap is reported)
  - "What does the LLM add over a for-loop?" (diagnosis from error slices and an action choice with a written rationale, all logged; it is not used for training)
  - "Is the run reproducible if the LLM changes?" (yes, replay from the ledger)

### D7. Revised timeline
| Week | Work |
|---|---|
| 1 | Day-1 data gate; Ingestion + Profiler + EDA agents; refine problem from Phase-I |
| 2 | Cleaner, Feature builder, Leakage Guard, Splitter; baselines B0/B1 |
| 3 | Trainer + Evaluator + Critic loop; M1–M3; ledger |
| 4 | Tester, Explainer, LOCO + stress tests; frontend |
| 5 | Reporter draft → human-edited report, slides, viva rehearsal |

**What to cut if time runs short:** M4 LSTM → Reporter agent → React (fall back to Streamlit) → LOCO. **Never cut:** the locked test set, the Leakage Guard, the baselines.

---

## Related agentic-ML research (for the report's literature section)
- [AIDE: AI-Driven Exploration in the Space of Code (2025)](https://arxiv.org/pdf/2502.13138): tree search over ML solutions
- [AutoKaggle (2024)](https://arxiv.org/pdf/2410.20424): multi-agent, phase-based data-science pipeline (closest to our design)
- [MLE-bench (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/hash/7e3767db483c942b883eb4f8cfb74e31-Abstract-Conference.html): benchmark for ML-engineering agents
- [LLM agents for cleaning tabular data (arXiv 2503.06664)](https://arxiv.org/pdf/2503.06664): finds LLMs fix row-level errors well but **struggle with distribution-level issues**. This supports our choice of rule-based cleaning.

## Items to verify on day 1
- [x] How far back the Vayuayan / OpenAQ station history goes → **see Part E: neither works as the main source**
- [x] Open-Meteo CAMS archived *issued-on-day-t* forecasts → **not available; see E2**
- [x] Open-Meteo ERA5 boundary-layer height for India → **works, with a Jan–Jun 2024 gap; see E3**
- [ ] NASA FIRMS map key and the area/date query limits
- [ ] Copernicus ADS account + `cdsapi` access to CAMS archived forecasts (E2 option B)
- [ ] Download the Kaggle Delhi dataset and read `DATA_DICTIONARY.md` / `STATION_COVERAGE.csv` (needs a Kaggle login)
- [ ] (P2) UCI macro features `nunique()`; OULAD table sizes after download

---

## Part E: Day-1 data gate results (run 2026-10-22)

All checks below were run live against the real endpoints. The probe scripts are in the session scratchpad.

### E1. Station pollutant data (the target)

| Source | What was checked | Result | Verdict |
|---|---|---|---|
| **Vayuayan archive** (`data.vayuayan.saketlab.org`) | `index.json` for all 648 stations | Every station's `first_timestamp` is **Nov 2025 or later**. It is a live-scrape archive. The extra "historical" files hold only about 50 AQI values per year (2017–2024; e.g. Anand Vihar has 369 days total) plus *monthly* satellite PM2.5. | ❌ **Fail** as training data. ✅ Usable only for a live "today" demo feed. |
| **OpenAQ S3 archive** (`openaq-data-archive`, no key) | Scanned location IDs 1–3000 for Indian stations; measured per-year daily-file counts | Older CPCB station IDs (Gurugram 301, Lucknow 2456, Chennai 2586, Mumbai 2582) have **no files at all for 2023–2024**, are patchy for 2018–2022 (87–211 days/year in several years) and are sparse within each day. Newer CPCB IDs probably exist, but finding them needs a free API key (the v3 API returns 401 without one). | ⚠ **Not suitable as the main source.** Good for a recent/live feed once you have a key. |
| **Kaggle: "Delhi Air Quality: CPCB Station Data (2010–2026)"** (`yug201/delhi-air-quality-cpcb-hourly-2010-2026`) | File listing via Kaggle API | **Hourly**, one CSV per station-year. **36 stations every year 2017–2025** (10 stations for 2010–2016), 37 in 2026. About 441 MB in total. The description says it also includes meteorological observations. Includes `DATA_DICTIONARY.md` and `STATION_COVERAGE.csv`. | ✅ **Pass. This becomes the core dataset.** |
| **Kaggle: "Time Series Air Quality Data of India (2010–2023)"** (`abhisheksjha/...`) | File listing via Kaggle API | 453 station files (UP 57, MH 41, DL 40, KA 39, …), about 1.7 GB, uploaded June 2023, so it **ends around mid-2023**. CC BY-NC-SA. | ✅ Usable for a **secondary multi-city transfer test** (2017–2022). |

### E2. CAMS physics forecast

| Check | Result |
|---|---|
| Open-Meteo `pm2_5` history for Delhi | Starts **2022-08-04**, with only 5 missing hours through 2025-10-15 |
| `pm2_5_previous_day1` / `_day2` (forecasts issued 1–2 days earlier) | The API accepts the variables but **returns all nulls** for 2022–2025 |
| Interpretation | The Open-Meteo history is a stitch of the newest model runs (close to an analysis of that hour). **Using its t+1 value as a feature would leak the future.** |

**Options:**
- **A (safe, zero setup):** use CAMS PM2.5 for **day t only**, as "what the physics model says about today". There is no leak, but it is not a forecast.
- **B (true MOS correction):** download archived forecasts at 24–48 h lead time from the **Copernicus Atmosphere Data Store**, dataset `cams-global-atmospheric-composition-forecasts` (2015–present, 0.4°, CC-BY). This needs a free ADS account and `cdsapi`, and I could not test it without an account.

**Plan:** try B in week 1 and fall back to A. P1 survives either way. If you use A, novelty item 2 becomes "ML vs a physics-informed feature".

### E3. ERA5 meteorology (Open-Meteo archive API)

| Check | Result |
|---|---|
| `boundary_layer_height` for Delhi, Pune and Kolkata, 2019-01-01 → 2025-10-15 | ✅ Real values (e.g. Delhi median 210 m, Pune 445 m, Kolkata 370 m) |
| Gaps | ❌ **One contiguous gap: 2024-01-01 05:00 → 2024-07-01 04:00** (4,368 hours), identical in every city. It is still missing with `models=era5`, `era5_seamless`, `ecmwf_ifs`, and in the historical-forecast API (which only has values from Sept 2024). |
| Other variables (wind etc.) | ✅ Returned with no gap |

**Fix:** either fill Jan–Jun 2024 directly from the Copernicus CDS ERA5 single-levels dataset (same free Copernicus account as E2-B), or keep that half-year out of the evaluation sets (see the revised split below).

### E4. What changes in the P1 plan

| Item | Before (Part A) | After the data gate |
|---|---|---|
| Main dataset | 12–20 stations in 6 cities via Vayuayan/OpenAQ | **36 Delhi CPCB stations, hourly, 2017–2025** (Kaggle `yug201`) |
| Geographic scope | Six cities | **Delhi-NCR focus.** This is also where stubble burning, SAFAR and most of the literature are, so the related-work comparison is direct. |
| Generalisation test | Leave-one-city-out | **Leave-one-station-out** within Delhi + **cross-city transfer** to Lucknow/Kanpur/Mumbai/Pune using the `abhisheksjha` 2017–2022 data |
| Split | Train 2019–22 / Val 2023 / Test 2024+ | **Train 2017–2022** (lockdown flagged) / **Val 2023 + Jul–Dec 2024** / **Test 2025 (locked)**. This skips the Jan–Jun 2024 ERA5 gap unless it is filled from CDS. |
| CAMS track | t+1 CAMS forecast from Open-Meteo | E2 option B (ADS archived forecasts) or option A (day-t CAMS) |
| Data size | ~36k station-days | **~36 stations × ~3,200 days ≈ 115k station-days** (hourly source ≈ 2.7M rows). Still laptop-scale after daily aggregation. |
| Live demo feed | — | Vayuayan (Nov 2025 onward, hourly) to show tomorrow's forecast for today |

**Revised P1 one-liner:** *Leakage-free next-day AQI-category forecasting for 36 Delhi CPCB stations (2017–2025), fusing station history, ERA5 meteorology, upwind crop-fire activity and the CAMS physics forecast, with leave-one-station-out and cross-city transfer tests.*

**Gate verdict: ✅ P1 passes, with a narrower geography and a Copernicus account as the one remaining dependency.**

### E5. Follow-up checks in the logged-in browser (2026-10-22)

**Kaggle Delhi dataset (read from its README and DATA_DICTIONARY, nothing downloaded):**
- Every station-year CSV has the same header. It contains 16 pollutant/VOC columns (PM2.5, PM10, NO, NO2, NOx, NH3, SO2, CO, Ozone, Benzene, Toluene, Xylene variants) **plus on-site meteorology**: AT (°C), RH (%), WS (m/s), WD (deg), RF / TOT-RF (mm), SR (W/m²), BP (mmHg), VWS (m/s).
  - **This changes the plan:** the station's own wind, humidity and temperature can be features directly. ERA5 is then needed mainly for **boundary-layer height** (and to fill gaps in station weather). That makes the Jan–Jun 2024 ERA5 gap less serious.
- Low saturation: about 180 views, 32 downloads and **0 public notebooks** (as of 2026-10-22). Almost no prior work uses this exact dataset, which is good for novelty.
- README caveats to handle in the Cleaner agent:
  - the **timezone of `Timestamp` is not stated**; assume IST, and confirm it against the diurnal PM2.5 peak (late evening/night in Delhi winter);
  - blanks and non-numeric placeholders must become NaN;
  - a missing station-year *file* means "not downloaded", not zero;
  - values are raw and not quality-controlled.
- 2023 has 36 station files, covering the CPCB, DPCC and IITM networks (e.g. ITO, R K Puram, Punjabi Bagh, Anand Vihar, Rohini, Okhla, Bawana, IGI Airport).
- Licence: "Other (specified in description)". The description asks you to cite CPCB as the original provider plus the Kaggle dataset version.
- **Still open:** per-station hourly missingness per column. This needs the actual files (440.6 MB), downloaded either via a Kaggle API token or the site's Download button.

**Copernicus ADS: `cams-global-atmospheric-composition-forecasts` download form:**
- Forecasts are issued at **00 and 12 UTC**, with **lead times 0–120 h, hourly**. A day-ahead feature is available: the 00 UTC run at lead time +24…+47 h covers tomorrow (IST is UTC+5:30).
- Formats: GRIB or zipped netCDF (experimental). Licence: CC-BY, and it **must be accepted on the dataset page once** before any API request works.
- ⚠ **"Dates more than 30 days old are slow access" (stored on tape).** Pulling 2022–2025 means tape retrievals. Keep the requests small: only `particulate_matter_2.5um`, a small Delhi box (`area = [29.0, 76.8, 28.3, 77.5]`), only the 00 UTC run, lead times 24–47 h, **one request per month**, queued in a background job. Expect hours of queue time, not minutes, so start this in week 1.
- ⚠ The browser pane was **not logged in** to ADS when checked ("Login/register to accept licences" was shown), so the licence acceptance and API key are still pending.

### E6. Delhi dataset downloaded and profiled (2026-10-22)

Downloaded to `data/raw/delhi_cpcb/` (422 MB, 431 station-year CSVs). All files share **one identical header**.

**Share of hours with a valid value (median across stations):**

| Year | PM2.5 | PM10 | NO2 | CO | O3 | AT | RH | WS | WD | BP |
|---|---|---|---|---|---|---|---|---|---|---|
| 2017 | **0** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2018 | 89 | 88 | 86 | 88 | 87 | 84 | 89 | 87 | 86 | 83 |
| 2019 | 97 | 96 | 96 | 96 | 96 | 97 | 97 | 97 | 97 | 98 |
| 2020 | 95 | 95 | 96 | 94 | 93 | 96 | 96 | 96 | 96 | 96 |
| 2021 | 95 | 95 | 96 | 93 | 95 | 96 | 97 | 97 | 97 | 96 |
| 2022 | 97 | 97 | 96 | 94 | 96 | 97 | 97 | 97 | 97 | 97 |
| 2023 | 95 | 95 | 95 | 94 | 93 | 95 | 96 | 95 | 96 | 95 |
| 2024 | 97 | 97 | 98 | 97 | 97 | 97 | 98 | 97 | 96 | 96 |
| 2025 | 96 | 96 | 98 | 97 | 97 | 98 | 98 | 97 | 96 | 96 |

- **33 of 36 stations have ≥70% hourly PM2.5 in *every* year 2019–2025.** 27 stations reach it in 8 or more of the 9 years 2017–2025.
- **2017 is mostly empty:** the files are padded to 8,760 rows, but the median station has 0% PM2.5. 2010–2016 (10 stations) is patchy at 0–68%. → **Start training in 2018.**
- **Timezone confirmed as IST:** the winter (Nov–Jan) median PM2.5 by hour peaks at **23:00 (236 µg/m³)** with its low at **16:00 (130 µg/m³)**, the expected Delhi diurnal cycle in local time.
- **Value checks (2023):** no non-numeric placeholders, no negatives, no duplicate timestamps. PM2.5 median is 67, 99th percentile 433. **The maximum is exactly 1000**, with 7 readings at ≥999. This is an instrument/reporting ceiling, so treat it as *censored* (cap it and flag it, don't delete). Rows are padded to the full year, so **blank = missing hour**.
- The station's own meteorology columns are as complete as the pollutants (≥95% from 2019), so **on-site weather replaces most ERA5 variables**. ERA5 is kept only for boundary-layer height.

**Final P1 split (replaces E4):** Train **2018–2022** (Mar–Jun 2020 lockdown flagged) / Validation **2023–2024** / **Test 2025 (locked)**. Because station weather is complete for 2024, the ERA5 Jan–Jun 2024 boundary-layer gap now affects only one feature. Fill it from CDS, or let LightGBM treat it as missing.

**Data size:** 33 stations × ~2,900 days (2018–2025) ≈ **96k station-days** after daily aggregation.

**Gate status:** ✅ Kaggle data confirmed. ✅ CAMS archive confirmed (see E7).

### E7. CAMS archived-forecast test (2026-10-22): ✅ PASS

The CC-BY licence was accepted on the ADS dataset page, and requests then go through with `cdsapi` (key in `~/.cdsapirc`).

| Request | Storage | Time | Size |
|---|---|---|---|
| 1 day, 00 UTC run of 2026-10-20, lead 24–47 h, PM2.5, Delhi box | recent (disk) | 41 s | 29 KB |
| 1 day, 00 UTC run of 2024-11-10, lead 24–47 h | old ("slow access" tape) | 57 s | 29 KB |
| **1 month** (Nov 2023, every 00 UTC run, lead 19–42 h) | tape | **87 s** | 44 KB |

- **The whole archive is cheap:** 2018–2025 is 96 monthly requests × ~1.5 min ≈ **2.5 hours** as one background job, under 5 MB in total. The "slow access" warning turned out not to matter for requests this small.
- **The file format works:** netCDF via `xarray` gives `pm2p5` in kg/m³ (× 1e9 → µg/m³), with `forecast_reference_time` = the issue time on day t and `valid_time` in **UTC**. **This is a true day-ahead forecast, so there is no leakage.**
- **Lead-time window:** IST is UTC+5:30, so the 00 UTC run covers tomorrow's IST calendar day at lead **≈19–42 h**. Use that window, and align by `valid_time` converted to IST.
- **Resolution:** 0.4° means only a **2×2 grid** (28.4/28.8°N × 76.8/77.2°E) covers Delhi. CAMS is a **city-scale** feature: each station takes its nearest cell (or bilinear interpolation).

**First evidence for the ML-correction novelty (one day only; not a result):**

| 11 Nov 2024 | Daily mean PM2.5 | Peak hour |
|---|---|---|
| CAMS forecast issued 10 Nov (nearest cell) | ≈103 µg/m³ | 14–16 UTC (≈ 19:30–21:30 IST) |
| Observed, median of 34 Delhi stations | **198 µg/m³** | 23:00–01:00 IST |

On this day CAMS forecast about half the observed concentration and its peak came a few hours early. That is exactly the kind of systematic bias an ML correction layer can learn. The Explainer/EDA agents should reproduce this comparison over 2018–2025 (bias by month and hour) before claiming it.

**Caveat:** CAMS is upgraded periodically (model cycle changes), so its bias is not constant over time. Add a "CAMS cycle" or year feature, or evaluate the bias per year.

### Data gate: final status
| Dependency | Status |
|---|---|
| Station pollutants + on-site weather (Kaggle, 33 stations, 2018–2025) | ✅ Downloaded and profiled |
| CAMS day-ahead forecasts (Copernicus ADS) | ✅ Tested for recent and old dates; the full pull is ≈2.5 h |
| ERA5 boundary-layer height (Open-Meteo) | ✅ Except Jan–Jun 2024 (fill from CDS or leave as missing) |
| NASA FIRMS fire counts | ⏳ Not tested yet (needs a free MAP_KEY) |
| Cross-city transfer set (Kaggle `abhisheksjha`, to 2023) | ⏳ Not downloaded (1.7 GB; only needed for the extension) |
