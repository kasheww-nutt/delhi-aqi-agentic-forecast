# Model comparison: every model, why LightGBM, and what CAMS added

All numbers come from the saved run ledgers in [docs/results/](results/):

- **`cams-full`**: the final run, with the CAMS forecast (45 features).
- **`full-era5`**: the same pipeline without CAMS (43 features).

Both use the same data, split and settings: train 2018–22 (58,920 rows), validation 2023–24 (24,161), locked
test 2025 (12,200).

**Metrics used**

- **Macro-F1** is the main metric. It scores all 6 categories equally, so a model can't win by only predicting
  the common ones.
- **VP/Severe recall**: the share of Very Poor or Severe days predicted as Very Poor or Severe.
- **Within ±1**: the share of predictions at most one category off.
- **Mean category error**: how many categories off a prediction is, on average.

## 1. Every model, every round (validation 2023–24)

**Final run, with CAMS (45 features)**

| Model | Round | Val macro-F1 | Train macro-F1 | VP/Severe recall | Accuracy | Within ±1 |
|---|---|---|---|---|---|---|
| Persistence | 1 & 2 | 0.587 | 0.578 | 0.846 | 0.648 | 0.966 |
| Logistic regression | 1 & 2 | 0.525 | 0.556 | 0.822 | 0.588 | 0.953 |
| Random forest | 1 & 2 | 0.588 | **0.969** | 0.862 | 0.674 | 0.971 |
| LightGBM | 1 | 0.589 | 0.805 | 0.831 | 0.653 | 0.971 |
| **LightGBM** | **2** | **0.594** | 0.758 | 0.836 | 0.647 | 0.973 |

- **Round 1 critic:** LightGBM was barely above persistence (0.589 vs 0.587) and worse on severe days, so it chose
  **`regularize_lgbm`**. The trainer made LightGBM simpler:
  - fewer leaves: 32 → 21;
  - more data needed per leaf: 23 → 79;
  - a stronger penalty: λ 0.27 → 8.9.
- **Round 2 critic:** the gain was only +0.005, under the 0.01 bar, so it chose **STOP**.
- Persistence, logistic regression and random forest are retrained each round with the same settings, so their
  scores don't change.

## 2. Why we chose LightGBM

| Model | Verdict |
|---|---|
| **Persistence** | The bar to beat ("tomorrow = today"); not a candidate. |
| **Logistic regression** | 0.525, **worse than doing nothing**. It can only learn straight-line rules, but pollution depends on thresholds and combinations of factors. |
| **Random forest** | 0.588, about level with persistence. Train 0.969 vs validation 0.588 shows it **memorised** the training years. |
| **LightGBM** | **Highest validation macro-F1 (0.594)**, and the only model that improved with the critic's fix. |

- **The rule was set in advance:** pick the model with the best validation macro-F1. The test year played no part
  in choosing.
- **Why LightGBM suits this data:**
  - it learns thresholds and combinations (low air "lid" + CAMS forecasting a rise → jump a category);
  - it handles missing values;
  - class weights make it pay attention to rare categories;
  - Optuna tunes it quickly.
- **Being honest:** random forest has slightly higher VP/Severe recall on validation (0.862 vs 0.836). But it's
  worse on the main metric and clearly overfit.

## 3. The locked 2025 test (scored once)

Only the selected model and persistence are scored on the test year.

| | Persistence | **LightGBM (with CAMS)** |
|---|---|---|
| Macro-F1 | 0.583 | **0.600** |
| VP/Severe recall | 0.845 | **0.860** |
| Accuracy | 0.654 | 0.651 |
| Within ±1 category | 0.968 | **0.980** |
| Mean category error | 0.380 | **0.371** |

**Recall per category:** what share of each category's days were predicted correctly.

| | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
|---|---|---|---|---|---|---|
| Persistence | 38% | 71% | **73%** | 41% | 67% | 59% |
| LightGBM | **51%** | 72% | 62% | **60%** | 67% | **69%** |

- LightGBM wins mostly on days when the **level changes**: Poor +19 points, Good +13, Severe +10.
- It loses on Moderate (−11), because it sometimes predicts a change that doesn't happen.
- Accuracy is about the same, but macro-F1 is higher, because the gains are spread across the rarer categories.

## 4. What CAMS added (the same pipeline, with vs without CAMS)

**Validation 2023–24**

| Model | Without CAMS | With CAMS |
|---|---|---|
| LightGBM (selected) | 0.589 | **0.594** |
| Random forest | 0.588 | 0.588 |
| Logistic regression | 0.537 | 0.525 |

**Locked 2025 test, LightGBM**

| | Without CAMS | **With CAMS** | Change |
|---|---|---|---|
| Macro-F1 | 0.574 (**loses** to persistence 0.583) | **0.600** (**beats** it) | **+0.026** |
| Accuracy | 0.628 | 0.651 | +0.023 |
| VP/Severe recall | 0.857 | 0.860 | +0.003 |
| Within ±1 | 0.975 | 0.980 | +0.005 |
| Mean category error | 0.399 | 0.371 | smaller mistakes |

| Recall | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
|---|---|---|---|---|---|---|
| Without CAMS | 52% | 71% | 59% | 59% | 60% | **73%** |
| With CAMS | 51% | 72% | **62%** | 60% | **67%** | 69% |

**What this shows**

- **CAMS is the difference between losing and winning.** Without it, the model is worse than "same as today".
- **The biggest gains are Very Poor (+7 points) and Moderate (+3).** CAMS warns about regional changes, like trapped
  winter air or incoming crop-fire smoke, that a station's own history can't see coming.
- **Fewer false alarms** (accuracy +2.3 points). Without CAMS the model guessed changes more often, which caught a
  few more Severe days (73% vs 69%) but got more days wrong overall.
- **Only LightGBM used CAMS well.** Random forest didn't move, and logistic regression got slightly worse. Using a
  biased, coarse forecast well needs a model that learns thresholds and combinations.
- **SHAP agrees:** `cams_pm25_tomorrow_mean` is the **5th most important feature** (0.181), right after the
  station's own recent levels: `aqi_t0` 0.369, `PM2.5_t0` 0.316, `aqi_roll7_mean` 0.210 and `city_aqi_mean_t0` 0.204.

## 5. Why use CAMS when its grid is so coarse?

- **The mismatch:**
  - CAMS cells are about 0.4° (~45 km) wide, but our stations are points.
  - We average the 2×2 cells over Delhi into **one city-wide value per day**, so all 34 stations get the same CAMS
    number, and it can't see local hotspots.
- **It answers a different question:**
  - The station's history says how polluted **this spot** is.
  - CAMS says whether the **whole region** will get better or worse tomorrow (wind, rain, the boundary-layer "lid",
    smoke moving in). Those drivers really are city-wide, so a coarse forecast suits them.
- **The model corrects CAMS; it doesn't copy it.**
  - CAMS's raw numbers are often biased. For example, it forecast 463 µg/m³ for 2 Jan 2018.
  - LightGBM learns how CAMS relates to what each station actually measured. This is the standard
    **Model Output Statistics (MOS)** idea: ML corrects a physics forecast with local observations.
  - Trees use rises, falls and thresholds, not exact values, so a consistent bias doesn't hurt.
- **Why not something finer?**
  - We need **archived forecasts** issued on each day of 2018–2025, or the test isn't honest. CAMS provides that
    for free.
  - The free Open-Meteo CAMS series is a reanalysis that already includes the target day's observations, so it
    would leak the answer.
- **Limits and future work:**
  - Use the nearest CAMS cell for each station instead of the city average.
  - Or use a finer regional forecast, if an archive of past forecasts becomes available.

## 6. The short version

> "We trained four models on the same features. Logistic regression fell below persistence and random forest
> overfit (train 0.97 vs validation 0.59). Tuned LightGBM had the best validation macro-F1, 0.594, after the critic
> regularised it. On the locked 2025 test it scored 0.600 vs 0.583 for persistence. The CAMS forecast is what made
> that possible: without it, the same model scored 0.574 and lost to persistence. CAMS is coarse, so we use it as
> one city-wide signal of tomorrow's regional conditions, and LightGBM learns to correct its bias for each station."
