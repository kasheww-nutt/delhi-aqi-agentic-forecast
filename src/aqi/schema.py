"""Canonical hourly schema — the contract every dataset must meet before it enters the pipeline.

It is exactly the layout of the Delhi CPCB dataset the pipeline was built on: one row per
(station, hour), naive local timestamps (IST), and these variables in these units.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TIMEZONE = "Asia/Kolkata"


@dataclass(frozen=True)
class Variable:
    name: str
    unit: str
    kind: str                       # pollutant | meteorology
    lo: float                       # physically plausible range (after conversion)
    hi: float
    aliases: tuple[str, ...] = field(default_factory=tuple)
    molar_mass: float | None = None  # g/mol, for ppb ⇄ µg/m³ conversion


VARIABLES = [
    Variable("PM2.5", "ug/m3", "pollutant", 0, 1000, ("pm25", "pm2_5", "fineparticulatematter", "pm2p5")),
    Variable("PM10", "ug/m3", "pollutant", 0, 2000, ("pm10", "coarseparticulatematter")),
    Variable("NO", "ug/m3", "pollutant", 0, 2000, ("no", "nitricoxide"), 30.01),
    Variable("NO2", "ug/m3", "pollutant", 0, 1000, ("no2", "nitrogendioxide"), 46.01),
    Variable("NOx", "ppb", "pollutant", 0, 2000, ("nox", "nitrogenoxides"), 46.01),
    Variable("NH3", "ug/m3", "pollutant", 0, 2000, ("nh3", "ammonia"), 17.03),
    Variable("SO2", "ug/m3", "pollutant", 0, 2000, ("so2", "sulphurdioxide", "sulfurdioxide"), 64.07),
    Variable("CO", "mg/m3", "pollutant", 0, 100, ("co", "carbonmonoxide"), 28.01),
    Variable("Ozone", "ug/m3", "pollutant", 0, 1000, ("o3", "ozone"), 48.00),
    Variable("Benzene", "ug/m3", "pollutant", 0, 500, ("benzene", "c6h6"), 78.11),
    Variable("Toluene", "ug/m3", "pollutant", 0, 1000, ("toluene",), 92.14),
    Variable("AT", "degC", "meteorology", -30, 55, ("at", "temp", "temperature", "airtemperature", "t2m", "tempc")),
    Variable("RH", "%", "meteorology", 0, 100, ("rh", "humidity", "relativehumidity", "relhum")),
    Variable("WS", "m/s", "meteorology", 0, 60, ("ws", "windspeed", "wspd", "wind")),
    Variable("WD", "deg", "meteorology", 0, 360, ("wd", "winddirection", "wdir")),
    Variable("RF", "mm", "meteorology", 0, 500, ("rf", "rain", "rainfall", "precip", "precipitation")),
    Variable("SR", "W/m2", "meteorology", 0, 1500, ("sr", "solarradiation", "radiation", "ghi", "globalradiation")),
    Variable("BP", "mmHg", "meteorology", 400, 820, ("bp", "pressure", "barometricpressure", "surfacepressure", "atmpressure")),
]
BY_NAME = {v.name: v for v in VARIABLES}
CANONICAL = [v.name for v in VARIABLES]
COLUMNS = ["timestamp", "station"] + CANONICAL

# Never imported. A source's own AQI is dropped because the pipeline recomputes AQI from the
# pollutants with CPCB rules; importing another system's index would mix two definitions.
IGNORE_AQI = ("aqi", "aqibucket", "aqicategory", "aqiindex", "airqualityindex")
IGNORE_EXTRA = ("xylene", "oxylene", "mpxylene", "ethbenzene", "totrf", "vws")
IGNORE = IGNORE_AQI + IGNORE_EXTRA

TIMESTAMP_NAMES = ("timestamp", "datetime", "datetimelocal", "date", "time", "datelocal", "fromdate", "obstime")
STATION_NAMES = ("station", "stationid", "stationname", "site", "siteid", "sitename", "location", "locationid",
                 "monitor", "monitorid")
PARAMETER_NAMES = ("parameter", "pollutant", "variable", "param", "species")
VALUE_NAMES = ("value", "concentration", "measurement", "reading")
UNIT_NAMES = ("unit", "units")


def norm(text: str) -> str:
    """'PM2.5 (µg/m³)' → 'pm25'; 'wind_speed' → 'windspeed'."""
    text = re.sub(r"[\(\[].*?[\)\]]", "", str(text))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def unit_in_header(header: str) -> str | None:
    m = re.search(r"[\(\[]([^\)\]]+)[\)\]]", str(header))
    return norm_unit(m.group(1)) if m else None


def norm_unit(u: str | None) -> str | None:
    if u is None:
        return None
    u = str(u).strip().lower().replace("µ", "u").replace("μ", "u").replace("³", "3").replace("²", "2")
    u = u.replace(" ", "").replace("°", "deg").replace("per", "/").replace("^", "")
    return {"ugm3": "ug/m3", "ug/m-3": "ug/m3", "mgm3": "mg/m3", "ngm3": "ng/m3", "w/mt2": "w/m2", "wm2": "w/m2",
            "c": "degc", "degreesc": "degc", "celsius": "degc", "f": "degf", "k": "kelvin", "kmph": "km/h",
            "kph": "km/h", "kt": "knots", "mb": "hpa", "mbar": "hpa", "degrees": "deg", "degree": "deg",
            "percent": "%"}.get(u, u)


MOLAR_VOLUME = 24.45  # L/mol at 25 °C, 1 atm (CPCB/WHO convention)


def converter(var: Variable, unit: str | None):
    """Return (factor_or_fn, description) converting `unit` to the canonical unit, or None if unknown."""
    target = norm_unit(var.unit)
    u = norm_unit(unit) or target
    if u == target:
        return (lambda x: x), "already canonical"
    mm = var.molar_mass
    linear = {
        # mass concentrations
        ("mg/m3", "ug/m3"): 1000, ("ng/m3", "ug/m3"): 1e-3, ("ug/m3", "mg/m3"): 1e-3, ("ng/m3", "mg/m3"): 1e-6,
        # meteorology
        ("km/h", "m/s"): 1 / 3.6, ("knots", "m/s"): 0.514444, ("mph", "m/s"): 0.44704,
        ("hpa", "mmhg"): 0.750062, ("kpa", "mmhg"): 7.50062, ("pa", "mmhg"): 0.00750062, ("inhg", "mmhg"): 25.4,
        ("cm", "mm"): 10, ("in", "mm"): 25.4, ("fraction", "%"): 100,
    }
    if (u, target) in linear:
        f = linear[(u, target)]
        return (lambda x, f=f: x * f), f"× {f:g}"
    if mm and u in ("ppb", "ppm") and target in ("ug/m3", "mg/m3"):
        f = mm / MOLAR_VOLUME * (1000 if u == "ppm" else 1) * (1e-3 if target == "mg/m3" else 1)
        return (lambda x, f=f: x * f), f"{u} → {var.unit} via molar mass {mm} (× {f:.4g})"
    if mm and target == "ppb" and u in ("ug/m3", "ppm"):
        f = 1000 if u == "ppm" else MOLAR_VOLUME / mm
        return (lambda x, f=f: x * f), f"{u} → ppb (× {f:.4g})"
    if target == "degc" and u == "degf":
        return (lambda x: (x - 32) * 5 / 9), "°F → °C"
    if target == "degc" and u == "kelvin":
        return (lambda x: x - 273.15), "K → °C"
    return None


def match_variable(header: str) -> Variable | None:
    key = norm(header)
    for v in VARIABLES:
        if key == norm(v.name) or key in v.aliases:
            return v
    return None
