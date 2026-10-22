import pandas as pd

from aqi.agents.splitter import assign

CFG = {"train": ["2022-01-01", "2022-12-31"], "val": ["2023-01-01", "2023-12-31"],
       "test": ["2024-01-01", "2024-12-31"]}


def test_rows_crossing_a_boundary_get_no_split():
    issue = pd.Series(pd.to_datetime(["2022-06-01", "2022-12-31", "2023-12-31", "2024-03-01"]))
    target = issue + pd.Timedelta(days=1)
    a, b = assign(issue, CFG), assign(target, CFG)
    split = a.where(a == b)
    assert split.tolist()[0] == "train"
    assert pd.isna(split[1]) and pd.isna(split[2])   # target falls in the next period
    assert split.tolist()[3] == "test"
