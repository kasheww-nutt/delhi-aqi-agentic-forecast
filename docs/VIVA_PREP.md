# Viva Prep (simple words)

Every term in **bold** is explained in [GLOSSARY.md](GLOSSARY.md). Every number has a source in [RESULTS.md](RESULTS.md).

---

## 1. The project in 30 seconds

- We forecast **tomorrow's air-quality category** (Good → Severe) for 34 Delhi monitoring stations.
- We use **only what is known today**, so there is no cheating with future data.
- The bar to beat is "tomorrow = today" (**persistence**). In Delhi this is hard, because pollution changes slowly.
- Our model, **LightGBM** plus the **CAMS** physics forecast, beats it on a **locked** 2025 test year:
  **macro-F1 0.600 vs 0.583**, 86% of Very Poor/Severe days caught, 98% of forecasts within one category.
- The whole thing runs as a pipeline of **14 agents**, with a **Leakage Guard** that stops the run if any
  feature uses the future.

## 2. The project in 2 minutes

1. **Problem.** Delhi's health warnings depend on next-day air-quality forecasts. Physics models (SAFAR, CAMS)
   are biased at street level. Many ML "AQI predictors" online use the same day's pollutant readings, so they
   don't actually forecast anything.
2. **Data.** 2.52 million hourly readings from 36 CPCB stations (2018–2025), plus ERA5 boundary-layer height
   (how much room pollution has to spread out) and the CAMS day-ahead PM2.5 forecast.
3. **Cleaning.** Fixed rules from a config file, all logged: remove impossible values, fill short gaps, compute
   daily AQI the official CPCB way. The target is never filled in.
4. **Features.** 45 features. Each one is registered with which day it describes, so the Leakage Guard can
   prove nothing comes from tomorrow (except things truly known today, like tomorrow's date or a forecast
   published today).
5. **Split by time.** Train 2018–22, validate 2023–24, test 2025. The test file is locked with a hash and
   opened once.
6. **Models.** Persistence, logistic regression, random forest and LightGBM, with balanced class weights.
   LightGBM is tuned with Optuna on a hold-out inside the training years.
7. **Critic loop.** A critic agent (an LLM, with a rule fallback) reads validation scores and picks one action
   from a fixed list. Code limits the loop to 4 rounds and stops when the gain is under 0.01.
8. **Result.** 0.600 vs 0.583 macro-F1 on 2025. Without CAMS, only 0.574, so the physics forecast is the key input.
9. **Explanation.** SHAP shows tomorrow depends mostly on today's level, plus the CAMS forecast of how it will change.

## 3. One-line novelty (memorise this)

> "Most AQI prediction work leaks same-day data and never beats persistence. We built a leakage-guarded
> agentic pipeline that forecasts the next day's category, corrects the CAMS physics forecast with ML, and
> beats persistence on a locked 2025 test year."

## 4. How the project covers the rubric (30 marks)

| Rubric row | Marks | What we did | Where to show it |
|---|---|---|---|
| Problem statement | 3 | Next-day category, only today's information, persistence as the bar; clear users (DPCC, CAQM, hospitals, schools) | Slide 2 |
| Dataset | 4 | 2.52M hourly rows, 34/36 stations, 18 variables, ERA5 + CAMS, quality audit, second dataset | Slides 3–4, DATA.md |
| Methodology | 5 | Feature registry, leakage guard, time split, locked test, critic loop with whitelist | Slides 5–7, METHODOLOGY.md |
| Implementation | 5 | 14 agents in LangGraph, ledger, CLIs for LLMs, FastAPI + React console, 18 tests, replay | Slide 8, live console |
| Results | 5 | Validation table, locked test, per-category recall, confusion matrix, SHAP, CAMS ablation | Slides 9–12, RESULTS.md |
| Report | 3 | Written by the team from these docs and the results snapshot | Report |
| Presentation | 2 | 15-slide deck + live console demo | Deck |
| Viva | 3 | This guide | — |

## 5. Why we made each choice

| Choice | Why (simple version) |
|---|---|
| Forecast the **category**, not the exact AQI number | Warnings and GRAP rules use categories. Also, a 6-class problem is easier to judge fairly. |
| **Persistence** as the baseline | It is free, and it's hard to beat because AQI changes slowly. Beating it proves the model adds value. |
| **Macro-F1** as the main metric | Every category counts equally. Accuracy would reward just predicting "Moderate" a lot. |
| **Very Poor/Severe recall** reported separately | Those are the days that trigger health warnings. Missing them is the costly mistake. |
| **Time split**, not random split | In real life you forecast the future from the past. A random split lets the model peek at neighbouring days. |
| **Locked, hashed test year** | So nobody (human or agent) can tune on the test by accident. The hash proves the file never changed. |
| **LightGBM** | Fast, strong on tables of numbers, handles missing values, and works with SHAP. |
| Also logistic regression and random forest | A linear model shows how much non-linearity helps; random forest is the standard robust comparison. |
| **Balanced class weights** | Good and Severe days are rare. Without weights, the model would mostly ignore them. |
| Tune on an **inner hold-out** (2022), not validation | So validation stays a fair score for the critic. |
| **CAMS forecast** as a feature | It knows about tomorrow's weather and emissions, which history alone cannot. |
| Only the CAMS **forecast issued today**, not reanalysis | Reanalysis already includes tomorrow's observations, which would be leakage. |
| **Rules** for cleaning, splitting, metrics | They must be correct and repeatable. LLMs can make mistakes and give different answers each time. |
| **LLM** only for notes, unknown columns and the critic | That's where judgement helps, and every LLM answer is boxed in by a schema and a whitelist. |
| LLMs via **CLIs**, not the paid API | No API bill: they run on the team's existing subscriptions. Answers are cached for exact replay. |
| **LangGraph** | It makes the order of agents, and the loop, explicit and easy to show. |
| A **ledger** | Every decision is written down, so the whole run can be audited and shown in the console. |

## 6. Likely viva questions, with short answers

### Problem and data
1. **Why next-day and not same-day?** Same-day AQI is just a calculation from today's readings. That's not a
   forecast. Warnings need to go out a day ahead.
2. **Why Delhi?** It has some of the world's worst air, a dense CPCB network, long history, and most Indian
   air-quality research to compare against.
3. **Why 2018–2025?** The 2017 files are almost empty, and 2025 is the latest complete year for testing.
4. **Why drop 2 stations?** They had PM2.5 on less than 70% of hours in too many years. A station with big gaps
   would give unreliable targets.
5. **What is the 1000 µg/m³ ceiling?** The instrument's maximum. Readings stuck there are real "very high"
   values, so we keep them and count them instead of deleting them.
6. **How do you handle missing data?** Short gaps (≤6 h) are interpolated within a station. A day needs ≥16
   valid hours. Remaining input gaps get station-month medians from training years only, plus a flag. The
   target is never filled in.
7. **Why medians from training years only?** Using later years to fill gaps would leak information about the
   future into the past.
8. **What is the class imbalance?** Moderate is about 35% of days, Good about 1.5%, Severe about 8.8%.

### Leakage
9. **What is leakage?** When the model gets information it would not have at forecast time. It makes scores
   look great in testing and fail in real use.
10. **How do you prevent it?** The feature registry (each feature's day offset), the Leakage Guard (3 checks),
    a time split with no shuffling, imputation from training years only, and a locked test year.
11. **The calendar features use tomorrow's date. Isn't that leakage?** No. Tomorrow's date, weekday and whether
    it's near Diwali are known today. They're registered as "known in advance".
12. **And CAMS describes tomorrow too?** Yes, but it is a forecast *published today* at 05:30 IST. We use the
    archived forecast exactly as it was issued, not the later reanalysis.
13. **Prove the guard works.** The leaky demo adds tomorrow's real PM2.5 as a feature, and the guard halts the
    run before any model sees it (RESULTS.md §6).
14. **What is the 97% tripwire?** If any AQI-type feature matches tomorrow's category on more than 97% of rows,
    it's almost certainly the answer in disguise, so the run stops.

### Models and results
15. **You only beat persistence by 0.017. Is that meaningful?** It's on 12,200 station-days scored once. And
    the gains are where it matters: Poor +19 points, Severe +10, Good +13, and more Very Poor/Severe days
    caught. Persistence is a strong baseline one day ahead, and that's expected.
16. **Accuracy is lower than persistence (0.651 vs 0.654). Why?** Persistence is very good on Moderate days,
    which are the most common, so it wins on accuracy. Our model is better on rarer and changing days, which
    macro-F1 captures.
17. **Did you beat the raw CAMS forecast?** We didn't score raw CAMS on its own. We showed that CAMS as a
    feature lifts the model from 0.574 to 0.600. Scoring raw CAMS directly is future work.
18. **Why does the model need CAMS?** History says where pollution is now. CAMS adds where it's heading (weather,
    winds, emissions). Without it, the model can't beat "tomorrow = today".
19. **Why is the random forest's training score 0.969?** It memorised the training data (overfitting). Its
    validation score of 0.588 shows it didn't learn general patterns.
20. **Why not deep learning (LSTM)?** Gradient-boosted trees are usually as good or better on tabular data,
    train in minutes on a laptop, and are easy to explain with SHAP. Deep learning is listed as future work.
21. **What does the confusion matrix show?** Almost all mistakes are one category off. The biggest is 1,034
    Moderate days forecast as Poor: the model leans towards early warnings, which is the safer mistake.
22. **What does SHAP say?** Today's AQI and PM2.5 matter most, then the 7-day average and city-wide AQI, then
    the CAMS forecast. So: today's level plus the physics forecast of change.
23. **Why tune on 2022 and not on validation?** Validation is what the critic uses to judge changes. Tuning on it
    too would make it optimistic and the critic would be fooled.
24. **Why refit on train + validation before testing?** More recent data helps forecast 2025. The setup was
    chosen before the refit, so the test stays fair.

### Agents and LLMs
25. **What makes it "agentic"?** Separate agents with clear jobs, a shared state, a loop where the critic
    decides the next step from results, and tools the agents call. It isn't one big script.
26. **What exactly does the LLM decide?** Only the critic's next action, from a fixed list (for example
    `regularize_lgbm`), plus written notes. It cannot change the data, split, metrics or test.
27. **What if the LLM gives a bad answer?** Its answer must match a JSON schema and the allowed list. If not,
    it is rejected and the rule-based critic decides.
28. **Does the result depend on the LLM?** No. Running with no LLM gives the same test result (0.600 vs 0.583);
    the rule critic made the same choice (RESULTS.md §7).
29. **Why use CLIs instead of an API?** No cost: they use existing subscriptions. Each call runs in an empty,
    read-only folder, and the answer is cached for exact replay.
30. **Who stops the loop, the LLM or code?** Code. At most 4 rounds, and stop when the gain is under 0.01. In
    our run, round 2 gained +0.005, so a rule stopped it.
31. **What's the ledger?** A file where every agent writes what it did and decided, with timestamps. The
    console and reports read only this file.
32. **What does the schema adapter do?** It maps a different dataset's columns and units onto our format, so the
    same pipeline can run on it. We tested it on a 2015–2020 dataset.

### Reproducibility and engineering
33. **Can someone reproduce your result?** Yes. Fixed seeds, the config hash is logged, the test file has a
    SHA-256 hash, LLM answers are cached, and REPRODUCE.md lists every command and the expected numbers.
34. **What do the tests cover?** 18 unit tests: AQI breakpoints, the leakage guard, the split boundaries, the
    schema adapter, and LLM CLI handling.
35. **How long does a run take?** About 6–8 minutes on a laptop.

## 7. Limitations (say them before they're asked)

- The gain over persistence is small, as expected one day ahead.
- Crop-fire data (NASA FIRMS) is not yet a model feature.
- The critic uses validation scores, so validation is slightly optimistic (the test year is not affected).
- One city only. ERA5 and CAMS are city-scale (~25–45 km), not station-scale.
- ERA5 boundary-layer height is missing for Jan–Jun 2024.
- The second dataset is small (5 usable stations).
- Raw CAMS was not scored as its own baseline, and LLM critic vs rule critic is not yet compared formally.

## 8. Future scope

1. Add upwind crop-fire counts from NASA FIRMS for October–November.
2. Score raw CAMS as a separate baseline, and compare the LLM critic with the rule critic over many runs.
3. Leave-one-station-out tests, and other cities through the schema adapter.
4. Calibrate probabilities so warnings can be issued at a chosen risk level.
5. Run daily on live CPCB and CAMS feeds.

## 9. Demo script (console)

Start it first: `uvicorn api.server:app --port 8000`, then open http://localhost:8000.

1. **Overview** (run `cams-full`): the headline 0.600 vs 0.583, Very Poor/Severe caught, the agent graph.
2. **Agent terminals:** click the critic. Show the exact CLI command, the prompt and the reply.
3. **Data:** the cleaner's decisions and the Leakage Guard's list of allowed future features.
4. **Training loop:** round 1 regularise, round 2 STOP by rule.
5. **Test year:** the confusion matrix and the day-by-day strip for one station.
6. **Drivers:** SHAP, with CAMS in the top five.
7. **The leaky run** in the run list: show that the guard halted it.

Backup: keep screenshots of each page in case the laptop or network fails.

## 10. Numbers to memorise

| What | Number |
|---|---|
| Test macro-F1, model vs persistence | **0.600 vs 0.583** |
| Without CAMS | 0.574 |
| Very Poor/Severe recall | 86% vs 84% |
| Within one category | 98% vs 97% |
| Accuracy | 0.651 vs 0.654 |
| Validation macro-F1 | 0.594 vs 0.587 |
| Test station-days | 12,200 |
| Train / val rows | 58,920 / 24,161 |
| Hourly rows | 2.52 million |
| Stations | 34 of 36 |
| Features | 45 |
| Agents | 14 |
| Tests | 18 |
| Critic rules | ≤4 rounds, stop if gain < 0.01 |
| Leakage tripwire | 97% agreement |
| Run time | about 6–8 minutes |
