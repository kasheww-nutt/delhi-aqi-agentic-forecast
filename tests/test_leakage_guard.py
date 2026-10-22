import numpy as np
import pandas as pd

from aqi.agents.leakage_guard import check

RNG = np.random.default_rng(0)


def _frame():
    y = RNG.integers(0, 6, 500).astype(float)
    return pd.DataFrame({"station": "s", "date": pd.Timestamp("2020-01-01"), "target_date": pd.Timestamp("2020-01-02"),
                         "target": y, "aqi_lag1": RNG.uniform(0, 500, 500), "dow_t1": RNG.integers(0, 7, 500)})


def test_clean_features_pass():
    reg = [{"name": "aqi_lag1", "group": "g", "offset": -1, "known_in_advance": False},
           {"name": "dow_t1", "group": "calendar", "offset": 1, "known_in_advance": True}]
    assert check(_frame(), reg) == []


def test_future_feature_is_blocked():
    reg = [{"name": "aqi_lag1", "group": "g", "offset": 1, "known_in_advance": False},
           {"name": "dow_t1", "group": "calendar", "offset": 1, "known_in_advance": True}]
    assert any("not known on day t" in p for p in check(_frame(), reg))


def test_unregistered_column_is_blocked():
    f = _frame().assign(mystery=1.0)
    reg = [{"name": "aqi_lag1", "group": "g", "offset": -1, "known_in_advance": False},
           {"name": "dow_t1", "group": "calendar", "offset": 1, "known_in_advance": True}]
    assert any("unregistered" in p for p in check(f, reg))


def test_empirical_tripwire_catches_a_disguised_target():
    f = _frame()
    f["aqi_lag1"] = f["target"].map({0: 25, 1: 75, 2: 150, 3: 250, 4: 350, 5: 450})  # target in disguise
    reg = [{"name": "aqi_lag1", "group": "g", "offset": -1, "known_in_advance": False},
           {"name": "dow_t1", "group": "calendar", "offset": 1, "known_in_advance": True}]
    assert any("matches tomorrow" in p for p in check(f, reg))
