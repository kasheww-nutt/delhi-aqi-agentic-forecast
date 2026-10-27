Here's what drives tomorrow's AQI category, ranked by mean |SHAP|:

- **Tomorrow mostly looks like today.** The top features are all versions of today's pollution: today's AQI (0.37), PM2.5 (0.32), the city-wide AQI mean and max (0.20 and 0.17), PM10 (0.15) and today's category (0.13). The 7-day rolling mean (0.21) adds a sense of the recent trend. Delhi's air changes slowly from day to day, so the strongest signal is simply "where are we now, and where have we been this week."

- **An outside forecast adds information the model can't get from its own data.** CAMS's PM2.5 forecast for tomorrow (mean 0.18, max 0.12) is the most important forward-looking input. It tells the model about incoming transport and emissions that today's sensor readings can't show yet.

- **Weather and season set the background.** A low boundary layer height (`blh_mean`, `blh_min`) traps pollutants near the ground, which is why winter nights are so bad. The day-of-year terms (`doy_sin/cos`) capture the seasonal cycle, such as the October–January peak from stubble burning and winter inversions. CO adds a small extra signal for combustion sources.

- **Flag: many top features measure the same thing.** About 8 of the 15 features are today's or recent AQI/PM in different forms (AQI, bucket, city mean and max, roll3, roll7, PM2.5, PM10). They are strongly correlated, so SHAP splits the credit between them somewhat arbitrarily. Read the ranking within this group loosely; the group as a whole ("persistence") is the real finding. Also, mean |SHAP| shows how much a feature matters but not which direction it pushes, and for a multiclass model it is averaged over the categories.

- **Flag: check for data the model wouldn't really have at forecast time.** These are the questions a viva panel is likely to ask:
  - **Today's values (`_t0`):** are today's AQI, PM and CO full-day values? If the forecast is issued during the day, the full-day value doesn't exist yet. Using it in training would be same-day leakage.
  - **CAMS:** is `cams_pm25_tomorrow` the forecast actually issued today, or a later reanalysis or analysis of tomorrow? The second would leak tomorrow's real conditions into the input.
  - **Boundary layer height:** if `blh` comes from ERA5 reanalysis, it is only published days later, so it can't be used operationally. A forecast product would be needed instead.
  - **Missing features:** wind speed and direction, fire counts and a Diwali/festival flag are not in the top 15. They are well-known drivers in Delhi, so check whether they were included at all.

**Bottom line:** the model is mainly a persistence forecast, with CAMS and the boundary layer adjusting it. It is believable if every input is truly available at forecast time. Leakage is the main thing to verify before the viva.