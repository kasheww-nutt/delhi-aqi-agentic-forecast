# Data

None of the raw data is committed (it is large and can be downloaded again). [REPRODUCE.md](REPRODUCE.md)
gives the download commands.

## 1. Sources

| Source | What it gives | Size / coverage | Access | Licence |
|---|---|---|---|---|
| **Delhi CPCB station data** (Kaggle `yug201/delhi-air-quality-cpcb-hourly-2010-2026`) | Hourly pollutants and on-site weather per station | 422 MB; 36 stations every year 2018–2025; 288 station-year CSV files | Kaggle API (free account) | see the Kaggle page |
| **ERA5 boundary-layer height** via the Open-Meteo archive API | Daily mean and min boundary-layer height at Delhi's centre (28.61 N, 77.21 E) | 2,922 days, 2018–2025; **Jan–Jun 2024 missing** at the source | Free, no key | ERA5: Copernicus licence |
| **CAMS global atmospheric composition forecasts** via the Copernicus Atmosphere Data Store (ADS) | Day-ahead PM2.5 forecast for Delhi, from the 00 UTC run issued on day t | 96 monthly downloads, 2018–2025; 0.4° grid (~45 km) | Free ADS account + `~/.cdsapirc` | CC-BY 4.0 (accepted on the ADS page) |
| **Air Quality Data in India (2015–2020)** (Kaggle, "Vopani") | Second dataset to test the schema adapter | 38 Delhi stations, hourly | Kaggle API | see the Kaggle page |

## 2. Variables (canonical schema)

One row per station-hour, timestamps in IST (Asia/Kolkata, confirmed from the daily PM2.5 cycle).
18 variables, defined in [`src/aqi/schema.py`](../src/aqi/schema.py):

- **11 pollutants:** PM2.5, PM10, NO, NO2, NOx, NH3, SO2, CO, Ozone, Benzene, Toluene.
- **7 weather variables:** air temperature (AT), relative humidity (RH), wind speed (WS), wind direction (WD),
  rainfall (RF), solar radiation (SR), barometric pressure (BP).

Each variable has a fixed unit and a physically possible range; values outside the range become missing.

## 3. How CAMS is turned into a feature without leakage

- CAMS publishes a new forecast every day at 00 UTC (05:30 IST).
- For the run issued on day t, lead times 19–42 hours cover all of day t+1 in IST.
- The 2×2 CAMS grid cells over Delhi are averaged into one city-wide series.
- From that, two features are built: the forecast **mean** and **max** PM2.5 for tomorrow.
- These are registered with offset +1 and `known_in_advance = true`: they describe tomorrow, but they were
  published on day t, so they are allowed.
- **Why not the free Open-Meteo CAMS series?** It is a reanalysis: it already includes observations from the
  target day, so it would leak the answer. Only archived *forecasts* are used.

## 4. Data quality findings

- **Station coverage:** 34 of 36 stations have PM2.5 on ≥70% of hours in ≥6 of the 8 years. Two IITM stations
  were dropped (Burari Crossing, Lodhi Road).
- From 2019 onward, the median station has 95–98% valid hours.
- 46 PM2.5 readings sit exactly at the 1000 µg/m³ instrument ceiling. They are kept as censored values.
- No negative readings were found in this dataset (the rule still exists for other datasets).
- The 2017 files exist but are almost empty, so the study starts in 2018.
- The target (tomorrow's category) is available for 96.0% of station-days.

### Class balance (station-days)

| Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
|---|---|---|---|---|---|
| 1,484 | 15,698 | 33,371 | 14,502 | 21,906 | 8,401 |

Good and Severe are rare, which is why every model uses balanced class weights and macro-F1 is the main metric.

## 5. Second dataset (schema adapter)

`scripts/adapt_dataset.py` maps a new dataset onto the canonical schema:

- detects the layout (wide or long), the timestamp, timezone, station column and time step;
- matches columns by alias (for example `O3` → Ozone, `pm2_5` → PM2.5) and converts units;
- asks an LLM about any column the rules cannot place; the answer must name a canonical variable and a
  convertible unit, or the column is dropped;
- never imports a source's own AQI column (we compute AQI ourselves, the same way for every dataset);
- rejects data without at least three pollutants, one of them PM2.5 or PM10;
- writes `canonical.parquet`, a `schema_report.json` with every decision, and a ready-to-run config.

On the Kaggle "Air Quality Data in India" Delhi data, the mapping took about 6 seconds, and the pipeline ran
with no code changes.
