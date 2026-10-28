# Data dictionary

All measurement tables have the following columns. Units are reproduced from the CPCB export headers.

| Column | Description | Unit |
|---|---|---|
| `Timestamp` | Reported date and time of the observation | source-provided datetime |
| `PM2.5 (µg/m³)` | Fine particulate matter with aerodynamic diameter ≤ 2.5 µm | µg/m³ |
| `PM10 (µg/m³)` | Particulate matter with aerodynamic diameter ≤ 10 µm | µg/m³ |
| `NO (µg/m³)` | Nitric oxide | µg/m³ |
| `NO2 (µg/m³)` | Nitrogen dioxide | µg/m³ |
| `NOx (ppb)` | Nitrogen oxides | ppb |
| `NH3 (µg/m³)` | Ammonia | µg/m³ |
| `SO2 (µg/m³)` | Sulfur dioxide | µg/m³ |
| `CO (mg/m³)` | Carbon monoxide | mg/m³ |
| `Ozone (µg/m³)` | Ozone | µg/m³ |
| `Benzene (µg/m³)` | Benzene | µg/m³ |
| `Toluene (µg/m³)` | Toluene | µg/m³ |
| `Xylene (µg/m³)` | Xylene | µg/m³ |
| `O Xylene (µg/m³)` | Ortho-xylene | µg/m³ |
| `Eth-Benzene (µg/m³)` | Ethylbenzene | µg/m³ |
| `MP-Xylene (µg/m³)` | Meta-/para-xylene | µg/m³ |
| `AT (°C)` | Air temperature | °C |
| `RH (%)` | Relative humidity | % |
| `WS (m/s)` | Wind speed | m/s |
| `WD (deg)` | Wind direction | degrees |
| `RF (mm)` | Rainfall | mm |
| `TOT-RF (mm)` | Total rainfall | mm |
| `SR (W/mt2)` | Solar radiation (label retained from source export) | W/mt2 |
| `BP (mmHg)` | Barometric pressure | mmHg |
| `VWS (m/s)` | Vertical wind speed | m/s |

## Filename fields

Example: `2024/site_301_Anand_Vihar_Delhi_DPCC_1Hr.csv`

| Filename component | Meaning |
|---|---|
| Parent directory (`2024`) | Calendar year associated with the file |
| `site_301` | CPCB/source site identifier |
| `Anand_Vihar_Delhi` | Station and city label as exported |
| `DPCC` | Reporting/operating agency label as exported |
| `1Hr` | Hourly frequency label |
