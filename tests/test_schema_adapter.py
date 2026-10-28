import numpy as np
import pandas as pd
import pytest

from aqi import schema as S
from aqi.agents.schema_adapter import NotAQData, adapt, suggest_settings

HOURS = pd.date_range("2021-01-01", periods=48, freq="h")


def test_aliases_and_header_units():
    assert S.match_variable("PM2.5 (µg/m³)").name == "PM2.5"
    assert S.match_variable("o3").name == "Ozone"
    assert S.match_variable("wind_speed").name == "WS"
    assert S.unit_in_header("CO (mg/m³)") == "mg/m3"
    assert S.match_variable("AQI") is None


def test_unit_conversions():
    fn, _ = S.converter(S.BY_NAME["NO2"], "ppb")
    assert fn(np.array([100.0]))[0] == pytest.approx(100 * 46.01 / 24.45)
    fn, _ = S.converter(S.BY_NAME["CO"], "ug/m3")
    assert fn(np.array([1500.0]))[0] == pytest.approx(1.5)
    fn, _ = S.converter(S.BY_NAME["BP"], "hPa")
    assert fn(np.array([1013.25]))[0] == pytest.approx(760, abs=0.1)
    assert S.converter(S.BY_NAME["PM2.5"], "furlongs") is None


def test_wide_file_with_other_names_units_and_an_aqi_column(tmp_path):
    pd.DataFrame({
        "Site ID": "S1", "Date Time": HOURS.astype(str), "pm2_5 [ug/m3]": 80.0, "PM10": 150.0,
        "no2 (ppb)": 20.0, "CO (ppm)": 1.0, "temperature (F)": 68.0, "AQI": 180,
    }).to_csv(tmp_path / "obs.csv", index=False)
    frame, rep = adapt(tmp_path, log=lambda m: None)
    assert list(frame.columns) == S.COLUMNS
    assert frame["NO2"].iloc[0] == pytest.approx(20 * 46.01 / 24.45, rel=1e-4)
    assert frame["CO"].iloc[0] == pytest.approx(28.01 / 24.45, rel=1e-4)
    assert frame["AT"].iloc[0] == pytest.approx(20, rel=1e-4)
    assert any(i["column"] == "AQI" for i in rep["ignored"])
    assert rep["granularity"] == "hourly"


def test_long_format_with_offsets_and_subhourly_readings(tmp_path):
    t = pd.date_range("2021-01-01", periods=96, freq="15min", tz="UTC")
    rows = [{"location_id": 7, "location": "Test site", "datetime": ts.isoformat(), "parameter": p, "units": u, "value": v}
            for ts in t for p, u, v in [("pm25", "µg/m³", 40.0), ("pm10", "µg/m³", 90.0), ("o3", "ppb", 30.0)]]
    pd.DataFrame(rows).to_csv(tmp_path / "long.csv", index=False)
    frame, rep = adapt(tmp_path, log=lambda m: None)
    assert rep["files_used"][0]["layout"] == "long"
    assert len(frame) == 24 + 1                      # 15-min UTC readings → IST hours
    assert frame["timestamp"].min() == pd.Timestamp("2021-01-01 05:00")
    assert frame["Ozone"].iloc[0] == pytest.approx(30 * 48.0 / 24.45, rel=1e-4)


def test_rejects_data_without_enough_pollutants(tmp_path):
    pd.DataFrame({"station": "S1", "timestamp": HOURS, "PM2.5": 50.0, "RH": 60.0}).to_csv(tmp_path / "x.csv", index=False)
    with pytest.raises(NotAQData):
        adapt(tmp_path, log=lambda m: None)


def test_split_follows_the_datasets_own_years():
    ts = pd.date_range("2015-01-01", "2020-06-30", freq="D")
    s = suggest_settings(pd.DataFrame({"timestamp": ts, "station": "a"}), "Delhi")
    # five full years (2020 is partial): one validation year, the last full year is the test
    assert s["split"]["test"][0].startswith("2019") and s["split"]["val"][0].startswith("2018")
    assert s["split"]["train"] == ["2015-01-01", "2017-12-31"]
    assert s["groups"]["cams_forecast"] is True


def test_console_lists_the_accepted_schema():
    from fastapi.testclient import TestClient

    from api.server import app
    s = TestClient(app).get("/api/schema").json()
    assert [v["name"] for v in s["variables"]] == S.CANONICAL
    no2 = next(v for v in s["variables"] if v["name"] == "NO2")
    assert {"ug/m3", "ppb", "ppm"} <= set(no2["accepts"])
    assert "aqi" in s["ignored_aqi"] and "csv" in s["formats"]
