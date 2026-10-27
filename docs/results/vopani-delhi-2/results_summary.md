# Run vopani-delhi-2 — results summary

## Training loop (validation 2023–2024)

| Iter | Best model | Val macro-F1 | Persistence | Critic action |
|---|---|---|---|---|
| 1 | random_forest | 0.495 | 0.503 | regularize_rf |
| 2 | random_forest | 0.499 | 0.503 | STOP |

Selected: **random_forest** from iteration 2 (groups: ['pollutant_history', 'station_meteorology', 'calendar', 'city_context', 'era5_blh']).

## Locked test (2025) — evaluated once

| Model | Macro-F1 | Severe recall | Accuracy | Within ±1 category |
|---|---|---|---|---|
| persistence | 0.489 | 0.819 | 0.596 | 0.934 |
| random_forest | 0.480 | 0.769 | 0.573 | 0.944 |

Confusion matrix (random_forest, rows = actual, columns = predicted):

| | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
|---|---|---|---|---|---|---|
| **Good** | 0 | 2 | 0 | 0 | 0 | 0 |
| **Satisfactory** | 1 | 112 | 46 | 3 | 2 | 0 |
| **Moderate** | 1 | 104 | 328 | 132 | 27 | 5 |
| **Poor** | 0 | 2 | 102 | 170 | 38 | 12 |
| **Very Poor** | 0 | 0 | 29 | 114 | 278 | 71 |
| **Severe** | 0 | 0 | 1 | 18 | 53 | 137 |
