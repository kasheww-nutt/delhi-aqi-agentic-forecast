# Glossary (simple words, with a project example)

## Machine learning basics

- **Machine learning (ML):** a program that learns patterns from examples instead of following hand-written
  rules. *Here: it learns from 2018–22 how today's readings relate to tomorrow's category.*
- **Supervised learning:** learning from examples that come with the right answer. *Each row has tomorrow's
  real category as its answer.*
- **Classification:** predicting a group or label instead of a number. *We predict one of six AQI categories.*
- **Regression:** predicting a number. *We could predict the AQI value, but warnings use categories.*
- **Ordinal classes:** categories with a natural order. *Good < Satisfactory < … < Severe, so being one off is
  better than being three off.*
- **Feature:** one input column the model uses. *`aqi_t0` = today's AQI.*
- **Target (label):** what the model must predict. *Tomorrow's category.*
- **Training set:** data the model learns from. *2018–2022.*
- **Validation set:** data used to compare models and settings. *2023–2024.*
- **Test set:** data kept aside until the very end, used once. *2025.*
- **Overfitting:** the model memorises training data instead of learning general patterns. *Random forest:
  0.969 on training, 0.588 on validation.*
- **Underfitting:** the model is too simple to capture the pattern. *Logistic regression scores lower than the
  trees.*
- **Regularisation:** limits on a model so it can't memorise. *Fewer leaves and more samples per leaf for LightGBM.*
- **Hyperparameters:** settings chosen before training, like the number of trees or the learning rate.
- **Hyperparameter tuning:** trying settings to find the best ones. *Optuna, 15 trials.*
- **Class imbalance:** some classes are much rarer than others. *Good is about 1.5% of days.*
- **Class weights:** making mistakes on rare classes count more during training. *We use balanced weights.*
- **Cross-validation:** splitting data into several folds and rotating which one is held out. *We don't use
  random folds, because time order matters.*
- **Time-ordered split:** train on the past, test on the future, no shuffling. *Our split.*
- **Imputation:** filling missing values. *Station-month medians from training years.*
- **Interpolation:** filling a gap by drawing a straight line between known values. *Gaps up to 6 hours.*
- **Seed:** a fixed starting number for randomness, so runs repeat exactly. *Seed 42.*

## Models

- **Baseline:** the simple method any real model must beat.
- **Persistence:** forecast tomorrow = today. *Our baseline: 0.583 macro-F1 on 2025.*
- **Logistic regression (multinomial):** a linear model that gives a probability for each class.
- **Decision tree:** a flowchart of yes/no questions on features that ends in a prediction.
- **Random forest:** many decision trees trained on random samples, which then vote.
- **Gradient boosting:** trees built one after another, each fixing the previous ones' mistakes.
- **LightGBM:** a fast gradient-boosting library from Microsoft. *Our selected model.*
- **GBDT:** gradient-boosted decision trees, the family LightGBM belongs to.
- **Optuna:** a library that tunes hyperparameters automatically.
- **TPE (Tree-structured Parzen Estimator):** Optuna's method of picking the next settings to try, based on
  which earlier settings scored well.
- **Inner hold-out:** a slice inside the training data used only for tuning. *The year 2022.*
- **Refit:** training again on more data once the settings are chosen. *On train + validation before testing.*

## Metrics

- **Accuracy:** share of forecasts that are exactly right. Misleading when classes are imbalanced.
- **Precision:** of the days we predicted as class X, how many really were X.
- **Recall:** of the days that really were class X, how many we caught.
- **F1 score:** a balance of precision and recall (their harmonic mean).
- **Macro-F1:** the F1 of each class, averaged equally. *Our main metric, so rare classes count fully.*
- **Weighted F1:** F1 averaged by how common each class is.
- **Very Poor/Severe recall:** of the days that were really Very Poor or Severe, the share we forecast as Very
  Poor or Severe. *86%.*
- **Within one category:** share of forecasts at most one category off. *98%.*
- **Mean category error:** the average number of categories we are off by. *0.371, lower is better.*
- **Confusion matrix:** a table of actual class vs predicted class, showing exactly which mistakes happen.
- **Ablation:** removing one part to see how much it matters. *Removing CAMS: 0.600 → 0.574.*

## Leakage and honest evaluation

- **Data leakage:** the model sees information it would not have at forecast time, so test scores are falsely
  high.
- **Target leakage:** an input is basically the answer. *Predicting today's AQI from today's pollutants.*
- **Look-ahead (temporal) leakage:** using data from after the forecast time.
- **Hindsight leakage:** using information that only became known later (like today's news about past days).
- **Issue day (t):** the day the forecast is made.
- **Target day (t+1):** the day being forecast.
- **Day offset:** which day a feature describes, relative to t. *`aqi_lag1` has offset −1.*
- **Known in advance:** facts about tomorrow that are truly known today. *Tomorrow's weekday, a forecast
  published today.*
- **Feature registry:** our list of every feature with its group and day offset.
- **Leakage Guard:** our agent that checks the registry and halts the run if anything could leak.
- **Tripwire:** a simple safety check. *Any AQI-type input matching tomorrow's category on more than 97% of
  rows stops the run.*
- **Locked test set:** a test file that only one agent can read, once.
- **SHA-256 hash:** a fingerprint of a file. If even one byte changes, the fingerprint changes. *The tester
  refuses to run if the test file's hash changed.*

## Explainability

- **Explainable AI (XAI):** methods that show why a model made its prediction.
- **SHAP:** gives each feature a share of the credit for each prediction, based on game theory (Shapley values).
- **Mean |SHAP|:** the average size of a feature's effect across all predictions. *`aqi_t0` = 0.369, the largest.*
- **Feature importance:** a ranking of which inputs the model relies on most.

## Air quality and atmosphere

- **AQI (Air Quality Index):** one number from 0 to 500 summarising air pollution. CPCB's version takes the worst
  pollutant's sub-index.
- **Sub-index:** a pollutant's concentration converted to the AQI scale using official breakpoints.
- **Breakpoints:** the concentration limits that mark where each AQI category starts and ends.
- **CPCB:** Central Pollution Control Board, India's national pollution regulator. Runs the station network.
- **CAAQMS:** continuous ambient air quality monitoring stations, the automatic stations that give hourly data.
- **AQI categories:** Good (0–50), Satisfactory (51–100), Moderate (101–200), Poor (201–300), Very Poor
  (301–400), Severe (401+).
- **PM2.5 / PM10:** particles smaller than 2.5 / 10 micrometres. PM2.5 goes deep into the lungs and drives
  Delhi's winter AQI.
- **NO2, SO2, CO, O3, NH3:** nitrogen dioxide, sulphur dioxide, carbon monoxide, ozone, ammonia.
- **µg/m³:** micrograms per cubic metre, the unit of concentration.
- **Boundary layer (BLH):** the lowest layer of air, where pollution mixes. When it's shallow (cold winter
  nights), pollution is trapped near the ground.
- **Ventilation index:** boundary-layer height × wind speed. Low means the air can't clear. *Our
  `ventilation_t0` feature.*
- **ERA5:** a global weather dataset (reanalysis) from Europe's ECMWF. *We use its boundary-layer height via
  Open-Meteo.*
- **Reanalysis:** a best reconstruction of past weather, built from observations. Good for history, but it
  includes data from after any given forecast time.
- **CAMS:** Copernicus Atmosphere Monitoring Service, Europe's global air-quality forecast system.
- **Physics (numerical) forecast:** a forecast made by simulating the atmosphere with equations, not by
  learning from data.
- **Lead time:** how far ahead a forecast is for. *CAMS lead 19–42 hours covers our tomorrow.*
- **MOS (Model Output Statistics):** correcting a physics forecast's errors with statistics. *Our ML layer is a
  student-scale version of this.*
- **SAFAR:** IITM Pune's official air-quality forecasting system for Indian cities.
- **GRAP:** Graded Response Action Plan, Delhi's rules for emergency steps (construction bans etc.) as AQI worsens.
- **CAQM / DPCC:** the Commission for Air Quality Management (NCR) and the Delhi Pollution Control Committee.
- **Stubble burning:** farmers in Punjab and Haryana burning crop waste, mainly October–November.
- **NASA FIRMS:** NASA's satellite fire-detection service. *Future feature for crop fires.*
- **Censored value:** a reading stuck at the instrument's limit. The true value may be higher. *46 PM2.5 readings
  at 1000 µg/m³.*

## Agentic AI and LLMs

- **LLM (large language model):** an AI model trained on text that can read and write language. *Claude, Gemini,
  GPT.*
- **Agent:** a component with one clear job that reads the shared state and writes its result. *14 in our
  pipeline.*
- **Rule-based agent:** an agent that follows fixed code. *The cleaner.*
- **LLM agent:** an agent that asks an LLM for part of its decision. *The critic.*
- **Agentic pipeline:** a workflow made of agents that pass work along and can loop based on results.
- **Orchestrator:** the part that decides which agent runs next.
- **LangGraph:** a Python library for building agent workflows as a graph of steps.
- **State graph / state machine:** steps (nodes) connected by arrows (edges), sharing one state, with rules
  for which step comes next.
- **Shared state:** the information every agent can read and update. *Paths, feature groups, round history.*
- **Conditional edge:** a branch in the graph. *The critic goes back to the trainer, or on to the tester.*
- **Critic loop:** train → evaluate → critic decides → repeat, until a stop rule fires.
- **Whitelist:** a fixed list of allowed actions. *The critic can only choose from it.*
- **Guardrail:** a limit that keeps an AI safe or correct. *Whitelist, schema, round cap, minimum gain.*
- **Prompt:** the text instructions sent to an LLM.
- **System prompt:** the standing instructions that define the agent's role.
- **JSON schema:** a strict description of the shape an answer must have. Answers that don't fit are rejected.
- **Structured output:** an LLM answer in a fixed format (JSON) instead of free text.
- **Hallucination:** when an LLM states something false with confidence. Schemas and whitelists limit the damage.
- **Fallback:** what happens when the LLM doesn't answer properly. *The rule-based critic.*
- **CLI (command-line interface):** a program you run by typing commands. *`claude -p`.*
- **Headless mode:** running a CLI tool without a person typing into it. *Our pipeline calls the CLIs this way.*
- **Coding-agent CLI:** an AI assistant that runs in the terminal. *Claude Code, Gemini CLI, Codex, agy.*
- **API:** a way for programs to talk to a service over the internet. *The paid Anthropic API, which we avoid.*
- **Cache / replay:** saving each LLM answer so a run can be repeated exactly without calling the LLM again.
- **Sandbox:** a restricted space where a program can't harm anything else. *Each CLI call runs in an empty,
  read-only folder.*
- **MCP (Model Context Protocol):** a standard way to give an LLM extra tools. *Used by the v1.1 source scout,
  not in v1.0.*

## Engineering

- **Pipeline:** a sequence of steps that turns raw data into results.
- **Config file (YAML):** a text file holding every setting. *`configs/delhi.yaml`.*
- **Config hash:** a fingerprint of the config, logged at the start of each run.
- **Ledger:** our log file (`ledger.jsonl`) where every agent records what it did and decided.
- **JSONL:** a file with one JSON object per line.
- **Parquet:** a fast, compressed file format for tables.
- **Artifact:** any output file of a run: plots, models, summaries.
- **Schema (data):** the agreed set of columns, names and units. *18 canonical variables.*
- **Schema adapter:** our agent that maps another dataset onto our schema.
- **Unit test:** a small automatic check that one piece of code works. *18 tests.*
- **FastAPI:** a Python library for building web APIs. *Serves the console's data.*
- **React / TypeScript / Vite:** the tools used to build the web console.
- **Reproducibility:** someone else can rerun the work and get the same numbers.
