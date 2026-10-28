# Delhi Air Quality: CPCB Hourly Station Data (2010–2026)

## Overview

This collection contains hourly air-quality, meteorological, and selected volatile-organic-compound observations for monitoring stations in Delhi, India. The source data were retrieved from the Central Pollution Control Board (CPCB) monitoring portal and are stored as one CSV file per **year × monitoring station**.

The collection is intended for air-pollution trend analysis, exposure research, forecasting, spatial comparisons, quality-control studies, and reproducible data-science work.

## File layout

```
data/
├── 2010/
│   └── site_<site_id>_<station>_<agency>_1Hr.csv
├── …
├── 2026/
│   └── site_<site_id>_<station>_<agency>_1Hr.csv
├── DATA_DICTIONARY.md
├── STATION_COVERAGE.csv
└── _download_log.csv
```

Each observation file contains readings for one station in one calendar year. The station identifier, station name, operating agency, and frequency (`1Hr`) are embedded in its filename.

## Coverage and an important limitation

There are 432 station-year files spanning 2010–2026. Monitoring coverage changes through time: 10 stations are represented in 2010–2016, 36 in most years from 2017 onward, and 37 in 2026. **A station not represented for a year has no downloaded file for that station-year; this must not be interpreted as a measured zero, an hourly missing value, or proof that the site was inactive.** Use `STATION_COVERAGE.csv` to select the station-years actually present before building panels or calculating summary statistics.

The 2026 directory may contain a partial calendar year, depending on when the source was retrieved.

## Data structure

Every station-year CSV uses the same header. `Timestamp` identifies the reported observation time; all remaining fields are measurements. Units are included directly in the column names and documented in `DATA_DICTIONARY.md`.

Typical analysis workflow:

1. Read the required station-year files.
2. Parse `Timestamp` as a datetime (do not assume a timezone unless confirmed from the source export).
3. Retain the filename-derived station identity when combining files.
4. Convert non-numeric placeholders or blank cells to missing values.
5. Account for unequal station and temporal coverage in comparisons.

## Provenance

Source: Central Pollution Control Board (CPCB), Government of India, air-quality monitoring data export.

`_download_log.csv` records the collection run, source station label, status, and downloaded file size. It is a provenance aid, not a measurement table.

## Caveats

- This is a source-data collection. Values have not been imputed, calibrated, or independently validated here.
- Availability of pollutant fields can vary within a file; blanks should be handled as missing values.
- Differences between stations or years can reflect changes in monitoring coverage, instrumentation, or reporting as well as environmental conditions.
- Consult CPCB documentation before using this dataset for regulatory, health, or other high-stakes conclusions.

## Citation

Please cite the Central Pollution Control Board (CPCB), Government of India, as the original data provider and cite this Kaggle dataset version used in your work.
