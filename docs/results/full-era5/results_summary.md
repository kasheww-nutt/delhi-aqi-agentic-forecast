# Run full-era5 — results summary

## Training loop (validation 2023–2024)

| Iter | Best model | Val macro-F1 | Persistence | Critic action |
|---|---|---|---|---|
| 1 | random_forest | 0.588 | 0.587 | regularize_lgbm |
| 2 | lightgbm | 0.589 | 0.587 | STOP |

Selected: **lightgbm** from iteration 2 (groups: ['pollutant_history', 'station_meteorology', 'calendar', 'city_context', 'era5_blh']).

## Locked test (2025) — evaluated once

| Model | Macro-F1 | Severe recall | Accuracy | Within ±1 category |
|---|---|---|---|---|
| persistence | 0.583 | 0.845 | 0.654 | 0.968 |
| lightgbm | 0.574 | 0.857 | 0.628 | 0.975 |

Confusion matrix (lightgbm, rows = actual, columns = predicted):

| | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
|---|---|---|---|---|---|---|
| **Good** | 85 | 69 | 7 | 1 | 0 | 1 |
| **Satisfactory** | 252 | 1627 | 371 | 45 | 1 | 0 |
| **Moderate** | 21 | 685 | 2687 | 1034 | 90 | 2 |
| **Poor** | 0 | 10 | 292 | 980 | 337 | 41 |
| **Very Poor** | 0 | 1 | 46 | 426 | 1570 | 550 |
| **Severe** | 0 | 1 | 12 | 24 | 222 | 710 |
