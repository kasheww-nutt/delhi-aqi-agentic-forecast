# Methodology

## 1. The task

- **Input:** everything known about a station by the end of day *t* (the issue day).
- **Output:** the station's CPCB AQI category on day *t+1*: Good, Satisfactory, Moderate, Poor, Very Poor or
  Severe (classes 0–5, in order).
- **One row** = one station on one issue day. The target is the next calendar day's observed category at the
  same station. If the next day is missing, the row is dropped.
- **Baseline to beat:** persistence, "tomorrow's category = today's category". AQI changes slowly, so this is
  a strong baseline.

## 2. AQI calculation (CPCB National AQI, 2014)

- Sub-index per pollutant by linear interpolation between CPCB breakpoints:
  `I_p = (I_hi − I_lo) / (BP_hi − BP_lo) × (C_p − BP_lo) + I_lo`.
- PM2.5, PM10, NO2, SO2 and NH3 use 24-hour means; CO and O3 use the day's maximum 8-hour mean.
- Overall AQI = the highest sub-index. It is valid only with at least three pollutants, one of them PM2.5 or PM10.
- Categories: 0–50 Good, 51–100 Satisfactory, 101–200 Moderate, 201–300 Poor, 301–400 Very Poor, 401+ Severe.
- Code: [`src/aqi/aqi_index.py`](../src/aqi/aqi_index.py), tested in `tests/test_aqi_index.py`.

## 3. Cleaning (rules from the config, every decision logged)

1. Negative readings become missing. PM2.5 at the 1000 µg/m³ instrument ceiling is kept and counted (46
   readings), not deleted.
2. Any variable missing in more than 60% of the panel is dropped (none were).
3. Gaps of up to 6 hours are interpolated within one station only.
4. A daily mean needs at least 16 valid hours. Wind direction is averaged as a unit vector (sin, cos);
   rainfall is summed.
5. The daily AQI and category (the **target**) come from observed values only. The target is never imputed.
6. Remaining input gaps are filled with station-month medians computed on **2018–2022 only** (the training
   years), plus a missing-count flag and a PM2.5-missing flag.

## 4. Features (45, each registered with a day offset)

| Group | Count | Offset from day t | Examples |
|---|---|---|---|
| Pollutant history | 24 | 0 or earlier | `aqi_t0`, `PM2.5_t0`, lags 1/2/3/7 days, 3- and 7-day rolling mean and std |
| Station weather | 8 | 0 | temperature, humidity, wind speed, wind direction (sin, cos), rain, solar radiation, pressure |
| Calendar | 5 | +1 known in advance (4), 0 (1) | tomorrow's day of week, day of year (sin, cos), Diwali window; lockdown flag |
| City context | 3 | 0 | Delhi-wide mean and max AQI today, station minus city |
| ERA5 boundary layer | 3 | 0 | boundary-layer height mean and min, ventilation (BLH × wind speed) |
| CAMS forecast | 2 | +1 known in advance | CAMS forecast of tomorrow's mean and max PM2.5, issued on day t |

Every feature is recorded in a **feature registry** (`feature_registry.json`) with its group, offset and a
`known_in_advance` flag. A feature about day t+1 is allowed only if its value is genuinely known on day t: a
calendar fact, or a forecast that was issued on day t.

## 5. Leakage Guard (can halt the run)

Before any split or training, the guard checks three things and stops the pipeline if any fails:

1. **Registry check:** every column in the feature table is registered. Undocumented inputs cannot slip in.
2. **Time check:** no feature refers to a day after t unless it is marked known in advance.
3. **Tripwire:** any AQI-scale input that matches tomorrow's category on more than 97% of rows is treated as a
   leak. (Today's category, `bucket_t0`, is exempt: it is the persistence forecast itself.)

## 6. Time-ordered split

| Set | Period | Rows | Used for |
|---|---|---|---|
| Train | 2018–2022 | 58,920 | fitting; the last year is the inner hold-out for tuning |
| Validation | 2023–2024 | 24,161 | model comparison and the critic loop |
| Test (locked) | 2025 | 12,200 | scored once at the end |

- No shuffling. A row is kept only if both its issue day and its target day fall in the same period.
- The COVID lockdown (25 Mar–30 Jun 2020) stays in training, with a flag feature.
- The test file is written to `runs/<id>/locked/`, hashed with SHA-256, and never put in the shared state. Only
  the tester reads it, and it refuses to run if the hash has changed.

## 7. Models

| ID | Model | Why it is here |
|---|---|---|
| B0 | Persistence | the honest baseline every forecaster must beat |
| M1 | Multinomial logistic regression | linear reference; shows how much non-linearity is needed |
| M2 | Random forest (300 trees) | robust non-linear model |
| M3 | LightGBM (gradient-boosted trees) | strong on tabular data, handles missing values, tunable |

- **Class imbalance:** balanced class weights for every model (Good and Severe are rare).
- **Tuning:** Optuna, 15 TPE trials, on an **inner hold-out** (the last training year, 2022). Validation is
  never used for tuning, so it stays an honest signal for the critic.
- **Missing values:** median imputation for logistic regression and random forest; LightGBM handles gaps natively.
- **Final fit:** the tester refits the chosen setup on train + validation, then scores 2025 once.

## 8. Critic loop (validation only)

- After each round, the evaluator scores all models on validation. The critic then chooses **one** action from
  a whitelist: `widen_lgbm_search`, `regularize_lgbm`, `regularize_rf`, `unweighted_classes`,
  `toggle:<feature group>` or `STOP`.
- The LLM must answer in a fixed JSON schema; an action outside the list is rejected and the rule-based critic
  decides instead.
- Rules enforced in code, which the LLM cannot override: at most 4 rounds, and stop as soon as a round improves
  validation macro-F1 by less than 0.01.
- The critic never sees test data and cannot change the split, metrics or labels.

## 9. Metrics

- **Macro-F1 (primary):** the average F1 across the six categories, each counted equally. Rare categories matter
  as much as common ones.
- **Very Poor/Severe recall:** share of truly Very Poor or Severe days forecast as Very Poor or Severe.
- **Accuracy** and **weighted F1:** reported, but they favour the common Moderate days.
- **Within one category:** share of forecasts at most one category off.
- **Mean category error:** average number of categories the forecast is off by (lower is better).
- **Per-category recall** and the **confusion matrix**.
- **SHAP** (mean absolute value per feature) for the final LightGBM model.

## 10. Where LLMs are used, and where they are not

| Agent | LLM role | Fallback when no LLM answers |
|---|---|---|
| schema_adapter | places columns the rules could not recognise | column is dropped |
| eda | writes notes from summary statistics only | plots and stats without notes |
| critic | chooses one whitelisted action | rule-based critic |
| explainer | writes plain-language notes on SHAP results | SHAP chart and table only |

Loading, cleaning, features, the leakage guard, splitting, training, metrics and testing are all rules. They
must be repeatable and correct, so no LLM touches them.
