# Run v1-check-nollm — results summary

## Training loop (validation 2023–2024)

| Iter | Best model | Val macro-F1 | Persistence | Critic action |
|---|---|---|---|---|
| 1 | lightgbm | 0.589 | 0.587 | regularize_lgbm |
| 2 | lightgbm | 0.594 | 0.587 | STOP |

Selected: **lightgbm** from iteration 2 (groups: ['pollutant_history', 'station_meteorology', 'calendar', 'city_context', 'era5_blh', 'cams_forecast']).

## Locked test (2025) — evaluated once

| Model | Macro-F1 | Severe recall | Accuracy | Within ±1 category |
|---|---|---|---|---|
| persistence | 0.583 | 0.845 | 0.654 | 0.968 |
| lightgbm | 0.600 | 0.860 | 0.651 | 0.980 |

Confusion matrix (lightgbm, rows = actual, columns = predicted):

| | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
|---|---|---|---|---|---|---|
| **Good** | 83 | 69 | 9 | 1 | 0 | 1 |
| **Satisfactory** | 196 | 1661 | 391 | 45 | 2 | 1 |
| **Moderate** | 8 | 608 | 2802 | 1034 | 65 | 2 |
| **Poor** | 0 | 10 | 282 | 1001 | 338 | 29 |
| **Very Poor** | 0 | 2 | 39 | 425 | 1733 | 394 |
| **Severe** | 1 | 0 | 12 | 21 | 268 | 667 |
