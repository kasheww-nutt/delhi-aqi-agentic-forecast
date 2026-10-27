# AUCML (TE7483) ESE Project Audit: 5 Candidate Projects

**Goal:** choose a project that has real-world impact, isn't overdone (so we can still claim something new), and can score full marks on every row of the ESE rubric (30 marks).

---

## 1. What the rubric actually rewards

| # | Component | Marks | What gets "Excellent" | What it means for project choice |
|---|-----------|------:|-----------------------|----------------------------------|
| 1 | Problem Refinement & Use Case | 3 | Objective, scope, domain, **stakeholders**, real-world relevance; **refined from Phase-I** | Pick a problem with obvious users (a college, a hospital, a city). Show what changed since Phase-I. |
| 2 | Dataset, Preprocessing, Features | 4 | Source, size, attributes, target, dtypes, **missing values**, preprocessing, **feature engineering**, **validation strategy** | A messy-but-public dataset works *in your favour*: it gives you real preprocessing to show. A perfectly clean CSV leaves you little to talk about here. |
| 3 | Methodology & Pipeline | 5 | Full pipeline + **justification of chosen algorithms** | Every model needs a "why". Baseline → linear → tree ensemble is easy to justify. |
| 4 | Implementation | 5 | Complete, **reproducible**, clean structure | Must run end-to-end on a laptop or Colab. No 50 GB datasets, no multi-day training. |
| 5 | Results & Comparative Analysis | 5 | Correct metrics + **comparison** | You need ≥3 models plus a baseline, and a metric that suits the task (F1/PR-AUC for imbalance, MAE for regression). |
| 6 | Report | 3 | Problem, method, data, results, conclusion, **future scope, references** | Standard structure. |
| 7 | Presentation | 2 | Clear, visual, time-managed | Choose a project that has good plots (maps, time series, SHAP). |
| 8 | Viva | 3 | **Limitations & future scope**, deep understanding | The novelty must be something **you can explain in two sentences** and defend. |

**Key insight:** 15 of 30 marks (rows 3, 4, 5) go to *pipeline, execution and comparison*. "Simple novelty" should therefore be a change to **how the problem is framed or evaluated** (leakage-free setup, early-prediction, cost-sensitive thresholds, generalisation tests). That is cheap to build, easy to defend in the viva, and it directly produces extra comparison tables for row 5. A fancy new architecture would not do the same.

> **Phase-I note:** Row 1 explicitly grades refinement *from Phase-I*. If your Phase-I topic is close to one of these five, pick that one and present it as "Phase-I problem → refined problem".

---

## 2. Scoring legend for the audit

**Positioning scores (1–5):**
- **Impact:** how clearly the result helps a real stakeholder
- **Saturation:** how overdone it is on Kaggle/GitHub (**lower is better**: 1 = rare, 5 = Titanic-level)
- **Novelty headroom:** how easily a defensible twist can be added
- **Feasibility:** laptop/Colab-friendly, clean public data, ~3–4 weeks of work
- **Viva safety:** how easy it is to defend (low risk of "this is trivial / your results are leaked")

**Rubric fit:** the expected level per ESE row if executed well (E = Excellent, G = Good). The **projected ceiling** assumes a well-executed project.

---

## 3. Summary scoreboard

| Rank | Project | Domain | Impact | Saturation ↓ | Novelty | Feasibility | Viva safety | Projected ceiling /30 |
|---:|---|---|:-:|:-:|:-:|:-:|:-:|:-:|
| **1** | **P1: Leakage-free next-day AQI category forecasting for Indian cities** | Environment / public health | 5 | 3 | 5 | 5 | 5 | **29–30** |
| 2 | P2: Staged early-warning system for student dropout | Education | 5 | 3 | 4 | 5 | 5 | 28–30 |
| 3 | P3: Fake job-posting detection with text + metadata fusion | Employment / fraud | 4 | 3 | 4 | 4 | 4 | 27–29 |
| 4 | P4: Calibrated, fairness-audited 30-day diabetic readmission risk | Healthcare | 5 | 2 | 4 | 4 | 3 | 26–29 |
| 5 | P5: Cost-aware predictive maintenance with failure-mode diagnosis | Manufacturing | 4 | 3 | 3 | 5 | 3 | 25–28 |

Projects we **avoided** because they are too well known to claim novelty: Titanic, Iris, house prices, telco churn, credit-card fraud (ULB), heart disease (Cleveland), crop recommendation, MNIST/CIFAR, IMDB sentiment, plain stock price prediction.

Topics we **avoided** because they are too niche or risky for a 2-credit course: raw EEG/genomics, satellite imagery segmentation, anything needing GPU-days or private/hospital data access.

---

## P1: Leakage-free next-day AQI category forecasting for Indian cities ⭐ Recommended

### Problem statement
> Most public "AQI prediction" models predict today's AQI from today's pollutant readings. But AQI is *computed* from those same readings, so the models look very accurate while solving nothing (target leakage). Citizens, schools and municipal bodies need to know **tomorrow's** air-quality category in advance, so they can issue advisories, reschedule outdoor activities and plan traffic restrictions. **This project builds a leakage-free model that forecasts the next day's AQI category (Good → Severe) for Indian cities using only information available today. It also tests whether the model generalises to a city it has never seen.**

**Stakeholders:** municipal corporations (e.g. PMC Pune), state pollution control boards, schools, hospitals and asthma patients, and citizens using AQI apps.

### Dataset
- **Air Quality Data in India (2015–2020)** (Kaggle, Vijay Rajkumar / "Vopani"), compiled from CPCB data. Use `city_day.csv`: about **29.5k rows, 26 cities**, daily readings.
- **Features:** PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3, Benzene, Toluene, Xylene, City, Date. **Target:** `AQI_Bucket` shifted by −1 day (6 classes).
- **Why it scores well on row 2:** heavy, uneven missingness (some pollutants are missing in more than half the rows, and some cities lack entire sensors). That gives you real imputation decisions to justify.

### Simple novelty (three cheap, defensible twists)
1. **Leakage audit as a contribution.** Train the "naive" same-day model (very high accuracy) next to your honest next-day model and **show the accuracy drop**. That one table explains why most online projects are wrong.
2. **Leave-One-City-Out (LOCO) validation:** can a model trained on 25 cities forecast a 26th city with no history? This matters for smaller Indian cities that have few monitoring stations.
3. **COVID-lockdown stress test:** hold out March–May 2020 as a natural distribution-shift test set and show how each model degrades.

### Pipeline
```
city_day.csv
  → EDA: missingness heatmap per city/pollutant, seasonality (Oct–Jan peak), city comparison
  → Cleaning: drop pollutants >60% missing (justify); per-city time-interpolation for short gaps;
              median-by-city-month for long gaps; add missing-indicator flags
  → Target: AQI_Bucket(t+1); drop rows with no next-day label
  → Feature engineering (all from day t and earlier):
        lags (t, t-1, t-2, t-7) of PM2.5/PM10/NO2/CO/AQI
        rolling mean/std (3, 7 days); day-of-week; month; season; festival flag (Diwali window)
        city target encoding (fit inside training folds only)
  → Split: TIME-BASED (train 2015–2018, val 2019, test 2020) — no random shuffling
           + LOCO cross-validation as the second experiment
  → Models:
        B0 Persistence baseline ("tomorrow = today's bucket")
        M1 Multinomial Logistic Regression (interpretable, linear reference)
        M2 Random Forest (non-linear, robust to leftover noise)
        M3 XGBoost / LightGBM (best for tabular data, handles missing values natively)
        (optional) M4 LSTM on 14-day windows, presented as an extension
  → Tuning: Optuna or RandomizedSearchCV with TimeSeriesSplit
  → Evaluation: Macro-F1 (primary; classes are imbalanced), weighted F1, confusion matrix,
        per-class recall for "Very Poor/Severe" (the classes that matter for public health),
        ordinal error (how many buckets off), MAE if you also regress AQI value
  → Explainability: SHAP global + per-city; "which lag drives tomorrow's AQI?"
  → Deliverable: Streamlit app — pick a city and today's readings, get tomorrow's category and the drivers
```

### Rubric audit
| Row | Fit | Why |
|---|:-:|---|
| 1 Problem (3) | E | Concrete stakeholders and a clear "why next-day". India and Pune relevance lands well with the panel. |
| 2 Dataset (4) | E | Real missingness, time-aware feature engineering and an explicit validation strategy, which covers every item in the Excellent descriptor. |
| 3 Methodology (5) | E | Baseline → linear → bagging → boosting, each easy to justify. The time-based split is itself a methodology point. |
| 4 Implementation (5) | E | About 30k rows; trains in seconds on a laptop. |
| 5 Results (5) | E | Three comparison axes: models, leaky vs honest, random vs LOCO vs lockdown. Very rich row 5. |
| 6 Report (3) | E | Natural structure; future scope = weather data, satellite AOD, hourly data. |
| 7 Presentation (2) | E | India map coloured by error, seasonal plots, SHAP. Very visual. |
| 8 Viva (3) | E | "Why not random split?" and "Why does accuracy drop?" are questions you *want* to be asked. |

**Risks:** the honest model's numbers look "worse" (Macro-F1 roughly 0.5–0.65 is realistic). Present this as the point of the project, not a weakness. Persistence is a strong baseline, so beating it by a few points is a real result.

---

## P2: Staged early-warning system for student dropout

### Problem statement
> Universities can only intervene with dropout if they identify at-risk students **early**. Most models use end-of-semester grades, which arrive too late to help. **This project builds a three-stage early-warning system: (S0) at enrolment, (S1) after semester 1, (S2) after semester 2. It measures how prediction quality improves at each stage, so an institution can choose the earliest stage that is reliable enough to act on.**

**Stakeholders:** academic counsellors, scholarship and finance offices, university administration. The project transfers directly to Indian universities (including ours).

### Dataset
- **UCI: "Predict Students' Dropout and Academic Success"** (Polytechnic Institute of Portalegre, Portugal). **4,424 students, 36 features.** Target: Dropout / Enrolled / Graduate (imbalanced: Graduate ≈ 50%, Dropout ≈ 32%, Enrolled ≈ 18%).
- Mixed feature types: demographic, socio-economic (scholarship, debtor, tuition up to date), macro (unemployment, inflation, GDP), and semester-wise curricular units.
- **Weakness for row 2:** no missing values. Compensate with encoding decisions (many high-cardinality coded categoricals such as course and parents' occupation, which need grouping) and engineered ratios.

### Simple novelty
1. **Feature-availability stages (S0/S1/S2):** the same pipeline trained on three feature subsets, mirroring when data actually becomes available. Most public notebooks use all features at once.
2. **Cost-sensitive threshold for "Dropout":** missing a dropout costs more than a false alarm, so pick the operating threshold from a counsellor-capacity constraint (e.g. "we can call the top 15% of students").
3. **Actionable explanations:** split SHAP drivers into *actionable* (tuition fees, units approved) and *non-actionable* (age, nationality) groups, so the explanation suggests an intervention.

### Pipeline
```
UCI CSV
  → EDA: class balance, dropout rate by course/scholarship/debtor, correlation of semester features
  → Preprocessing: group rare categories (course, occupations) ; one-hot / target encoding ;
        scale numerics for LR/SVM
  → Feature engineering: approval_rate_sem1 = approved/enrolled, grade_trend = sem2 − sem1,
        financial_stress = debtor OR NOT tuition_up_to_date, evaluations_without_approval ratio
  → Stage subsets: S0 (enrolment-only), S1 (+sem1), S2 (+sem2)
  → Validation: Stratified 5-fold CV + held-out 20% test ; SMOTE / class_weight compared INSIDE folds
  → Models: Majority baseline, Logistic Regression, Random Forest, XGBoost, (SVM optional)
  → Evaluation: Macro-F1, Dropout recall, PR-AUC (Dropout vs rest), confusion matrix,
        "recall@top-15%" for the counsellor-capacity scenario
  → Comparison table: model × stage (3 × 4 grid) → the core result
  → SHAP: actionable vs non-actionable drivers
  → Streamlit: counsellor dashboard ranking students by risk
```

### Rubric audit
| Row | Fit | Why |
|---|:-:|---|
| 1 | E | Very clear stakeholders, and it is relatable to the panel (they are academics). |
| 2 | G→E | Clean data means less to show on missing values. Feature engineering has to carry this row. |
| 3 | E | The staged design is a strong methodology story. |
| 4 | E | Small dataset; trivial to reproduce. |
| 5 | E | The model × stage grid plus the cost-sensitive analysis give a rich comparison. |
| 6–8 | E | Easy to explain; "Enrolled" being hard to predict is a good limitation to discuss. |

**Risks:** the dataset is moderately popular (it was a Kaggle Playground competition in 2024). Lean hard on the staged and cost-sensitive framing so the project does not look like a copied notebook.

---

## P3: Fake job-posting detection with text + metadata fusion

### Problem statement
> Fake job postings are used to harvest personal data and collect "registration fees", and fresh graduates are frequent targets. **This project detects fraudulent job postings by combining the posting's text with structural red flags (missing company profile, no logo, salary anomalies, telecommuting). It checks whether the fused model beats text-only and metadata-only models, and explains *why* a post was flagged.**

**Stakeholders:** job portals (Naukri, LinkedIn, Internshala), college placement cells, job seekers.

### Dataset
- **EMSCAD: "Real or Fake Job Posting Prediction"** (Kaggle; University of the Aegean). **17,880 postings, 866 fraudulent (≈4.8%).**
- Text fields (title, company_profile, description, requirements, benefits), categorical fields (employment_type, industry, function, location), binary fields (has_company_logo, telecommuting, has_questions), salary_range.
- Lots of missing text fields, and the missingness itself is predictive. That is good material for row 2.

### Simple novelty
1. **Three-way fusion comparison:** text-only (TF-IDF) vs metadata-only vs fused. Quantifies how much each signal type contributes.
2. **"Missingness as a signal":** explicit features for empty fields and text length, with an ablation table.
3. **Red-flag explanation report:** the top TF-IDF terms and SHAP metadata flags for each flagged post, presented as a checklist that a placement cell could use.

### Pipeline
```
fake_job_postings.csv
  → EDA: fraud rate by industry/country/employment type, word clouds real vs fake
  → Text cleaning: lowercase, strip HTML/URLs, stopwords, lemmatise ; concatenate fields
  → Metadata: missing-field flags, text lengths, salary parsed into min/max/missing, country from location
  → Features: TF-IDF (1–2 grams, ~20k features) + one-hot categoricals + numeric flags → sparse hstack
  → Validation: stratified 80/20 + stratified 5-fold CV ; class_weight='balanced'
  → Models: Dummy baseline, Multinomial NB (text), Logistic Regression, Linear SVM, LightGBM (metadata/fused)
        (optional extension: DistilBERT embeddings — mention as future scope if no GPU)
  → Evaluation: PR-AUC (primary), F1 on fraud class, recall@precision≥0.9, confusion matrix
  → Ablation table: text / meta / fused × models
  → Explainability: LR coefficients for terms, SHAP for metadata
  → Demo: paste a job posting, get a fraud probability and its red flags
```

### Rubric audit
| Row | Fit | Why |
|---|:-:|---|
| 1 | E | Strong impact story for students. |
| 2 | E | Text and tabular data together, missingness and imbalance: plenty to describe. |
| 3 | E | Clear justification (NB/LR for sparse text, trees for metadata). |
| 4 | G→E | Sparse matrix handling needs care, but it is still laptop-scale. |
| 5 | E | The ablation table is a strong comparison. |
| 6–8 | E/G | Limitation: the data is 2012–2014 and US-centric, so its transfer to Indian portals is unproven. Mention this upfront. |

**Risks:** many notebooks report around 98% *accuracy*. You must argue against accuracy on 95/5 data, which scores well if you do it explicitly. NLP adds viva surface area (TF-IDF, n-grams), so prepare those answers.

---

## P4: Calibrated, fairness-audited 30-day diabetic readmission risk

### Problem statement
> Hospital readmissions within 30 days are costly and often preventable. **This project predicts 30-day readmission risk for diabetic inpatients and audits whether the model is (a) calibrated, so that a predicted 20% really means 20%, and (b) equally reliable across age, gender and race groups, before it could ever be used for discharge planning.**

**Stakeholders:** hospital discharge planners, care coordinators, insurers.

### Dataset
- **UCI: "Diabetes 130-US Hospitals (1999–2008)"**: **101,766 encounters, about 50 features.** Target `readmitted` ∈ {<30, >30, NO}, binarised to <30 (≈11% positive).
- Very messy: `weight` is about 97% missing, `payer_code` and `medical_specialty` are heavily missing, ICD-9 diagnosis codes have hundreds of levels (group them into about 9 disease categories), and there are repeat patients (dedupe or group-split by `patient_nbr`).

### Simple novelty
1. **Patient-grouped split** (GroupKFold on patient_nbr) vs naive random split, showing the leakage from repeat patients.
2. **Calibration** (reliability curve, Brier score, isotonic/Platt) instead of AUC alone.
3. **Subgroup fairness table:** recall and false-positive rate per age band, gender and race.

### Pipeline
```
diabetic_data.csv
  → Clean: '?' → NaN ; drop weight/payer_code (justify) ; drop expired/hospice discharges
  → ICD-9 → 9 clinical groups ; medication change features ; prior-visit counts
  → GroupKFold by patient ; class_weight
  → Models: LR, Random Forest, XGBoost/LightGBM, (CatBoost — native categoricals)
  → Metrics: ROC-AUC, PR-AUC, recall@top-20%, Brier score, calibration curve
  → Fairness: metric-by-subgroup table ; SHAP drivers
```

### Rubric audit
| Row | Fit | Why |
|---|:-:|---|
| 1 | E | High-impact domain. |
| 2 | E | The best preprocessing story of all five. |
| 3 | E | Calibration and the grouped split are strong methodology points. |
| 4 | G | 100k rows with many categoricals: still fine, just slower. |
| 5 | G→E | **Hard ceiling:** ROC-AUC is typically only around 0.65–0.70 in published work. You must frame modest numbers well. |
| 8 | G | Examiners may ask about the ICD-9 grouping and clinical terms, so you need domain preparation. |

**Risks:** the low achievable AUC can look like failure to an examiner who only glances at the numbers. Best for a team that is comfortable defending "the problem is hard and here is why".

---

## P5: Cost-aware predictive maintenance with failure-mode diagnosis

### Problem statement
> Unplanned machine downtime is expensive, but over-maintaining machines is wasteful too. **This project predicts imminent machine failure from sensor readings, identifies *which* failure mode is likely (tool wear, heat dissipation, power, overstrain), and picks a decision threshold that minimises total expected maintenance cost.**

**Stakeholders:** plant maintenance engineers and MSME manufacturers (relevant to the Pune/Chakan industrial belt).

### Dataset
- **UCI: "AI4I 2020 Predictive Maintenance Dataset":** **10,000 rows, 14 columns**, 339 failures (≈3.4%). Includes product quality type (L/M/H), air and process temperature, rotational speed, torque, tool wear, and 5 failure-mode flags.
- **Important caveat:** the dataset is **synthetic**, and its failure modes follow known rules on derived quantities (power = torque × speed, temperature difference, wear × torque).

### Simple novelty
1. **Physics-informed features** (power, ΔT, strain) vs raw features: show how much domain features help, especially for linear models.
2. **Cost matrix** (missed failure = ₹X, unnecessary service = ₹Y), with the threshold chosen to minimise total cost instead of maximising F1.
3. **Two-stage model:** first "will it fail?", then "which failure mode?" (multi-label).

### Pipeline
```
ai4i2020.csv → drop IDs ; encode Type ; physics features
  → Stratified CV ; SMOTE vs class_weight comparison
  → Models: LR, Decision Tree, RF, XGBoost ; second stage: multi-label RF
  → Metrics: PR-AUC, F1, recall, cost curve vs threshold, per-mode F1
  → SHAP: verify the model has "rediscovered" the physical rules
```

### Rubric audit
| Row | Fit | Why |
|---|:-:|---|
| 1 | E | Clear industrial use case. |
| 2 | G | No missing values and synthetic data, so the dataset row is thinner. |
| 3–4 | E | Simple and reproducible. |
| 5 | E/G | Scores near 0.99 once physics features are added, which is impressive but invites a "too easy" question. |
| 8 | G | **Viva risk:** "Your data is synthetic and rule-generated; what did ML actually learn?" Only choose this if you can answer that convincingly. |

---

## 4. Recommendation

**Go with P1 (leakage-free next-day AQI forecasting).** It is the only candidate where:
- the **novelty is a correction of a common flaw**, which is easy to prove with one table and hard for an examiner to dismiss;
- the **dataset gives full material for row 2** (missingness, time-aware features, an explicit validation strategy);
- the **comparison in row 5 has three independent axes** (models, leaky vs honest, random vs LOCO vs lockdown);
- the **topic is visibly local and relevant** (Indian cities, CPCB categories, winter smog), which helps row 1 and the presentation.

**Fallback: P2 (staged dropout early-warning)**, if the team prefers a smaller, cleaner dataset and an education framing. It is lower risk but gives slightly less to say on preprocessing.

### Suggested 4-week plan (for whichever project you pick)
| Week | Work | Rubric rows covered |
|---|---|---|
| 1 | Refine problem from Phase-I, finalise stakeholders, EDA and data dictionary | 1, 2 |
| 2 | Preprocessing + feature engineering + baseline + validation design | 2, 3 |
| 3 | Models, tuning, the novelty experiments, SHAP | 3, 4, 5 |
| 4 | Streamlit demo, report (incl. future scope and references), slides, viva Q&A prep | 6, 7, 8 |

### Repo structure (for reproducibility in row 4)
```
project/
  data/raw/  data/processed/
  notebooks/01_eda.ipynb  02_preprocessing.ipynb  03_modeling.ipynb  04_analysis.ipynb
  src/features.py  train.py  evaluate.py
  app/streamlit_app.py
  reports/figures/  report.pdf  slides.pdf
  requirements.txt  README.md   (with "how to reproduce" steps + random seeds fixed)
```

> Dataset sizes and class ratios above are from the public dataset descriptions. Re-verify them after downloading and report the exact numbers you observe in your report.
