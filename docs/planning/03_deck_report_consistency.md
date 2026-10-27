# Deck and report: fixes so they match v1.0

Checked against the run ledgers in `docs/results/`. Every core number in the deck matches (splits, validation
table, critic rounds, test table, per-category recall, confusion matrix, SHAP values, CAMS ablation, second
dataset, the 11 Nov 2024 CAMS example). The items below are wording, labels and visuals.

## Must fix (factually wrong)

| Slide | Now | Change to |
|---|---|---|
| 3, title | "Seven years of hourly Delhi data" | "Eight years…" (2018–2025) |
| 3, stat card | "19 attributes: 11 pollutants + 8 weather" | "18 attributes: 11 pollutants + 7 weather" (wind direction becomes 2 features later, which is where 8 came from) |
| 8, stack | "Anthropic SDK" | "Claude Code / Gemini / Codex / agy CLIs" |
| 8, subtitle and repo table | "14 unit tests" | "18 unit tests" (adds LLM CLI handling) |
| 8, reproducibility | "replays exactly without calling the API" | "…without calling any LLM" |
| 10, speaker notes | "only matches persistence at 0.574" | "falls just short of persistence (0.574 vs 0.583)" |
| 12, subtitle and notes | "Without CAMS the model only ties persistence" | "Without CAMS the model falls just short of persistence" |
| 12, SHAP chart | titled "Top inputs" but skips ranks 6–8 | show the true top 10, or retitle "Selected inputs" and show ranks (CAMS max is #9, ERA5 BLH #10) |

## Should fix (accuracy of detail)

| Slide | Issue | Fix |
|---|---|---|
| 4, feature table | Calendar shows offset "+1, known" for all 5 | 4 are +1 known in advance; the lockdown flag is offset 0 |
| 13 | "LLM critic effect not yet isolated" sits inside the "Small second dataset" box | give it its own line. Also add: the rule-only rerun gave the identical result (RESULTS.md §7) |
| 13 | FIRMS "not yet included" | keep for v1.0 (true). The v1.1 scout uses FIRMS for explanation only |

## Visual polish

- Slide 1: the "Persistence baseline" caption is hidden behind the GBDT card.
- Slide 3: the two dashboard thumbnails are unreadable. Crop to one chart or drop them.
- Slide 10: the bar chart starts at 0.50, which makes a +0.017 gap look large. Start at 0, or add "small gain".
- Slides 8–9: the console screenshots are too small. Crop to the part you talk about.

## New, worth adding

- A one-line novelty statement on slide 2 or 14 (see VIVA_PREP.md §3).
- Slide 9 or 13: "With no LLM, the rule critic made the same choice and the test result was identical."

## Timing

The speaker notes add up to about 21 minutes. If the slot is 8–10 minutes, cut slides 4, 6 and 9 to 30
seconds each, or merge them.

## References (for the documentation owner)

- Ref 2: check the author name for the Kaggle dataset `yug201` on the dataset page.
- Ref 3: the "Vopani" Kaggle account is believed to belong to Rohan Rao, not V. Rajkumar. Check the dataset page.
- Refs 6–8: add author names.
- Apply the same wording fixes to the report wherever the same claims appear (test count, LLM stack, "ties persistence", 18 variables, eight years).
