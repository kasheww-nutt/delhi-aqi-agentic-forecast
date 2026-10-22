import numpy as np
import pandas as pd

from aqi.aqi_index import bucket, overall_aqi, sub_index


def test_pm25_breakpoints_map_to_category_edges():
    conc = pd.Series([0, 30, 60, 90, 120, 250, 1000])
    assert sub_index("PM2.5", conc).tolist() == [0, 50, 100, 200, 300, 400, 500]


def test_overall_aqi_needs_three_pollutants_including_pm():
    sub = pd.DataFrame({"PM2.5": [150, 150, np.nan], "NO2": [80, np.nan, 80], "CO": [60, np.nan, 60],
                        "Ozone": [np.nan, np.nan, 40]})
    out = overall_aqi(sub)
    assert out[0] == 150
    assert np.isnan(out[1])          # only one pollutant
    assert np.isnan(out[2])          # three pollutants but no PM


def test_bucket_edges():
    assert bucket(pd.Series([0, 50, 51, 100, 200, 300, 301, 400, 401, 500])).tolist() == \
        [0, 0, 1, 1, 2, 3, 4, 4, 5, 5]
