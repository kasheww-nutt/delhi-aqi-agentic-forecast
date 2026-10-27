# Results

All numbers below come from the run ledgers saved in [`results/`](results/). They can be checked against
`results/results.json`, which is extracted directly from those ledgers.

| Run | What it is |
|---|---|
| `cams-full` | Final run: every feature group, including the CAMS forecast. **Headline result.** |
| `full-era5` | Ablation: the same pipeline with no CAMS forecast. |
| `vopani-delhi-2` | Second dataset (Kaggle "Air Quality Data in India", Delhi), run through the schema adapter. |
| `20261022-102940-leaky` | Leakage demo: tomorrow's PM2.5 added on purpose; the Leakage Guard stops the run. |
| `v1-check-nollm` | Release check: the frozen v1.0 code run again with `--no-llm` (rule-based critic only). |

## 1. Data that reached the models (`cams-full`)

| Step | Count |
|---|---|
| Hourly rows ingested (36 stations, 288 station-year files, 2018–2025) | 2,524,608 |
| Stations kept (PM2.5 present ≥70% of hours in ≥6 of 8 years) | 34 of 36 |
| Station-days after daily aggregation | 99,348 |
| Forecast rows with a valid next-day target | 95,348 |
| Rows in train / validation / test | 58,920 / 24,161 / 12,200 (total 95,281) |
| Features (all registered with a day offset) | 45 |

The 67 rows missing from the split total are pairs whose issue day and target day fall in different periods
(for example 31 Dec 2022 → 1 Jan 2023). They are dropped so that no label crosses a boundary.

Locked test file SHA-256 (`cams-full`): `b9d3dbfdcb06ad1cce947d0279563c8fabcf3496a96fc6c1e13fa46da937c3ce`.

## 2. Validation (2023–2024) and the critic loop

| Model | Val macro-F1 | Very Poor/Severe recall | Accuracy | Train macro-F1 |
|---|---|---|---|---|
| Persistence (tomorrow = today) | 0.587 | 0.846 | 0.648 | 0.578 |
| Logistic regression | 0.525 | 0.822 | 0.588 | 0.556 |
| Random forest | 0.588 | 0.862 | 0.675 | **0.969** |
| LightGBM, round 1 | 0.589 | 0.831 | 0.653 | 0.805 |
| **LightGBM, round 2 (selected)** | **0.594** | 0.836 | 0.647 | 0.759 |

- **Round 1.** The critic (answered by the Claude Code CLI) saw that LightGBM was barely above persistence and
  had a large train–validation gap (0.805 vs 0.589). From its whitelist it chose `regularize_lgbm`: at most 31
  leaves and at least 60 samples per leaf.
- **Round 2.** Validation macro-F1 rose by +0.005. That is below the 0.01 threshold, so **a rule in code, not the
  LLM**, stopped the loop.
- The random forest fits the training data almost perfectly (0.969) but scores only 0.588 on validation, a
  clear case of overfitting.

## 3. Locked 2025 test (scored once, 12,200 station-days)

| Metric | LightGBM + CAMS | LightGBM, no CAMS | Persistence |
|---|---|---|---|
| **Macro-F1** | **0.600** | 0.574 | 0.583 |
| Very Poor/Severe recall | **0.860** | 0.857 | 0.845 |
| Accuracy | 0.651 | 0.628 | **0.654** |
| Weighted F1 | **0.661** | — | 0.654 |
| Within one category | **0.980** | 0.975 | 0.968 |
| Mean category error (lower is better) | **0.371** | 0.399 | 0.380 |

- With CAMS, LightGBM beats persistence on every metric except plain accuracy, which is almost the same
  (0.651 vs 0.654). Accuracy rewards the common Moderate days, where persistence is strong. That is why
  macro-F1 and per-category recall are the headline metrics.
- **Without CAMS, the model falls just short of persistence** (0.574 vs 0.583). The physics forecast is what
  lets the model beat "tomorrow = today".
- "Very Poor/Severe recall" means: of the days that were actually Very Poor or Severe, the share the model
  forecast as Very Poor or Severe.

### Recall by category (2025)

| Category | Persistence | LightGBM + CAMS | Change |
|---|---|---|---|
| Good | 38% | 51% | +13 |
| Satisfactory | 71% | 72% | +1 |
| Moderate | **73%** | 62% | −11 |
| Poor | 41% | **60%** | +19 |
| Very Poor | 67% | 67% | 0 |
| Severe | 59% | **69%** | +10 |

The model gains most on days when the category changes (Good, Poor, Severe). Persistence stays better on
Moderate, the most common and most stable category.

### Confusion matrix, LightGBM + CAMS (rows = actual, columns = forecast)

| | Good | Satis. | Mod. | Poor | V.Poor | Severe |
|---|---|---|---|---|---|---|
| **Good** | 83 | 69 | 9 | 1 | 0 | 1 |
| **Satisfactory** | 196 | 1,661 | 391 | 45 | 2 | 1 |
| **Moderate** | 8 | 608 | 2,802 | 1,034 | 65 | 2 |
| **Poor** | 0 | 10 | 282 | 1,001 | 338 | 29 |
| **Very Poor** | 0 | 2 | 39 | 425 | 1,733 | 394 |
| **Severe** | 1 | 0 | 12 | 21 | 268 | 667 |

- 98.0% of forecasts are within one category of the truth.
- The largest single error is 1,034 Moderate days forecast as Poor. The model leans towards warning early,
  which is the cheaper mistake for health advisories.

## 4. What drives the forecast (SHAP, final model)

| Rank | Feature | Mean \|SHAP\| | Meaning |
|---|---|---|---|
| 1 | `aqi_t0` | 0.369 | today's AQI at the station |
| 2 | `PM2.5_t0` | 0.316 | today's PM2.5 |
| 3 | `aqi_roll7_mean` | 0.210 | 7-day average AQI |
| 4 | `city_aqi_mean_t0` | 0.204 | today's average AQI across Delhi |
| 5 | `cams_pm25_tomorrow_mean` | 0.181 | CAMS forecast of tomorrow's mean PM2.5 |
| 6 | `city_aqi_max_t0` | 0.172 | today's worst station in Delhi |
| 7 | `PM10_t0` | 0.154 | today's PM10 |
| 8 | `bucket_t0` | 0.134 | today's category |
| 9 | `cams_pm25_tomorrow_max` | 0.116 | CAMS forecast of tomorrow's peak PM2.5 |
| 10 | `blh_mean_t0` | 0.101 | ERA5 boundary-layer height today |

In short: tomorrow is explained by today's level plus the physics forecast of how it will change.

**Why CAMS needs correcting.** CAMS is a global model with ~45 km cells, so it smooths out street-level
peaks. On 11 November 2024, the CAMS forecast for the next day's Delhi mean PM2.5 was about 104 µg/m³; the
stations measured about 198 µg/m³. The model uses CAMS for the *direction of change* and today's station
readings for the *level*.

## 5. Second dataset (schema adapter)

- Dataset: Kaggle "Air Quality Data in India (2015–2020)", Delhi stations, hourly.
- The schema adapter mapped it onto the canonical schema; the pipeline then ran with no code changes.
- Only 5 of 38 stations had PM2.5 on ≥70% of hours in ≥3 years. Split: train 2,872 / val 1,679 / test 1,788
  rows (2019 test year).
- Test: random forest 0.480 vs persistence 0.489 macro-F1. Without a physics forecast the model again falls
  just short of persistence, the same pattern as Delhi without CAMS.

## 6. Leakage demo

Running with `--leaky-demo` adds `pm25_t1_LEAK` (tomorrow's observed PM2.5) as a feature. The Leakage Guard
stops the run before splitting or training:

> pm25_t1_LEAK uses day t+1 information that is not known on day t

## 7. Reproducibility check (release v1.0)

The frozen v1.0 code was run again from scratch with `--no-llm`, so the rule-based critic made every decision.

- Same split sizes, and the **same locked test hash** (`b9d3dbfdcb06…`): the test file was byte-for-byte identical.
- The rule-based critic chose the same action as the LLM critic in round 1 (`regularize_lgbm`, because of the
  train–validation gap), and the same stopping rule ended the loop in round 2.
- Same test result: **LightGBM 0.600 vs persistence 0.583 macro-F1**.

So the headline result does not depend on the LLM. The LLM adds explanations and a second opinion; the
guarantees come from code.

## 8. Honest limits of these results

- The win over persistence is real but small (+0.017 macro-F1). The gains are concentrated on the categories
  that matter for warnings (Poor +19 points, Severe +10).
- The raw CAMS forecast was not scored on its own as a separate baseline; CAMS is shown to help **as a feature**.
- The critic chooses actions using validation scores, so validation results are slightly optimistic. The
  locked test year is not affected.
- The comparison against the no-CAMS model comes from a separate run (`full-era5`) with the same code, data,
  split and seed.
