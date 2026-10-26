"""Schema adapter: turns any air-quality dataset that fits the use case into the canonical schema.

Rule-based first: layout (wide / long), timestamp, station and granularity detection, alias
matching, unit conversion and range checks. Columns the rules cannot place go to Claude, whose
answer must name a canonical variable and a convertible unit or the column is dropped. Every
decision is written to a schema report so the mapping can be reviewed in the console.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .. import schema as S
from ..config import resolve
from ..ledger import Ledger
from ..llm import LLM

READERS = {".csv": pd.read_csv, ".gz": pd.read_csv, ".parquet": pd.read_parquet, ".xlsx": pd.read_excel,
           ".xls": pd.read_excel}

LLM_SYSTEM = """You map columns of an air-quality dataset onto a fixed canonical schema for a next-day \
AQI forecasting pipeline. For each unknown column you get its header and value statistics. Answer with \
the canonical variable it measures and the unit its values are in, or "ignore" if it is not one of the \
canonical variables (identifiers, flags, indices such as AQI, other pollutants). Be conservative: \
ignore anything you are not confident about."""


class NotAQData(ValueError):
    """The input does not fit the use case (no timestamps, too few pollutants, ...)."""


def _files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in READERS
                  and not p.name.startswith(("_", ".")))


def _read(path: Path) -> pd.DataFrame:
    df = READERS[path.suffix.lower()](path, **({"low_memory": False} if path.suffix.lower() in (".csv", ".gz") else {}))
    df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    return df


def _find(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    by_norm = {S.norm(c): c for c in df.columns}
    return next((by_norm[n] for n in names if n in by_norm), None)


def _parse(s: pd.Series) -> pd.Series:
    ts = pd.to_datetime(s, errors="coerce")            # fast path: one inferred format
    if ts.notna().mean() < 0.9:
        ts = pd.to_datetime(s, errors="coerce", format="mixed")
    return ts


def _timestamp(df: pd.DataFrame) -> tuple[pd.Series | None, str]:
    col = _find(df, S.TIMESTAMP_NAMES)
    if col is not None:
        time_col = _find(df, ("time",)) if S.norm(col) == "date" else None
        if time_col and time_col != col:
            ts, col = _parse(df[col].astype(str) + " " + df[time_col].astype(str)), f"{col} + {time_col}"
        else:
            ts = _parse(df[col])
        if ts.notna().mean() > 0.9:
            return ts, col
    for c in df.columns:  # last resort: any text column that parses as dates
        if df[c].dtype == object and _parse(df[c].head(500)).notna().mean() > 0.95:
            return _parse(df[c]), c
    return None, ""


def _to_local(ts: pd.Series) -> tuple[pd.Series, str]:
    if getattr(ts.dt, "tz", None) is not None:
        return ts.dt.tz_convert(S.TIMEZONE).dt.tz_localize(None), f"converted from tz-aware to {S.TIMEZONE}"
    if ts.dtype == object:  # mixed offsets parse to objects
        return (pd.to_datetime(ts, utc=True).dt.tz_convert(S.TIMEZONE).dt.tz_localize(None),
                f"mixed offsets converted to {S.TIMEZONE}")
    return ts, f"naive timestamps assumed to be local time ({S.TIMEZONE})"


def _station(df: pd.DataFrame, path: Path) -> tuple[pd.Series, str]:
    cols = [c for c in df.columns if S.norm(c) in S.STATION_NAMES]
    ids = [c for c in cols if "id" in S.norm(c)]
    names = [c for c in cols if c not in ids]
    if ids and names:
        return df[ids[0]].astype(str) + "_" + df[names[0]].astype(str), f"{ids[0]} + {names[0]}"
    if ids:
        return df[ids[0]].astype(str), ids[0]
    if names:
        return df[names[0]].astype(str), names[0]
    stem = re.sub(r"(_1hr|_hourly|_daily)$", "", path.name.split(".")[0], flags=re.I)
    return pd.Series(stem, index=df.index), f"file name ({path.name})"


def _granularity(ts: pd.DataFrame) -> str:
    step = (ts.sort_values(["station", "timestamp"]).groupby("station")["timestamp"].diff().dt.total_seconds() / 60)
    med = step[step > 0].median()
    if pd.isna(med):
        return "unknown"
    return "subhourly" if med < 55 else "hourly" if med < 90 else "daily" if med >= 1380 else "irregular"


def _stats(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce")
    return {"non_null": float(round(x.notna().mean(), 3)), "min": _f(x.min()), "median": _f(x.median()),
            "max": _f(x.max()), "examples": [str(v) for v in s.dropna().head(3)]}


def _f(v):
    return None if pd.isna(v) else round(float(v), 3)


class Mapper:
    """Collects mapping decisions across all files of one dataset."""

    def __init__(self, llm: LLM | None):
        self.llm = llm
        self.mappings: dict[str, dict] = {}
        self.ignored: dict[str, str] = {}
        self.warnings: list[str] = []
        self._llm_cache: dict[str, dict | None] = {}

    def resolve_header(self, header: str, series: pd.Series, unit: str | None = None) -> dict | None:
        key = f"{header}|{unit}"
        if key in self.mappings:
            return self.mappings[key]
        if header in self.ignored:
            return None
        n = S.norm(header)
        if n in S.IGNORE_AQI:
            self.ignored[header] = "the source's own AQI; the pipeline recomputes AQI from pollutants (CPCB rules)"
            return None
        if n in S.IGNORE_EXTRA:
            self.ignored[header] = "measured, but not part of the canonical schema"
            return None
        var = S.match_variable(header)
        how = "alias"
        if var is None:
            if not pd.api.types.is_numeric_dtype(pd.to_numeric(series.head(200), errors="coerce").dropna()):
                self.ignored[header] = "not numeric"
                return None
            guess = self._ask_llm(header, series)
            if not guess:
                self.ignored[header] = "no canonical match" + ("" if self.llm else " (no LLM available)")
                return None
            var, unit, how = S.BY_NAME[guess["canonical"]], guess["unit"], f"llm ({self.llm.answered_by})"
        unit = unit or S.unit_in_header(header)
        conv = S.converter(var, unit)
        if conv is None:
            self.ignored[header] = f"{var.name}: unknown unit '{unit}'"
            return None
        fn, desc = conv
        x = fn(pd.to_numeric(series, errors="coerce"))
        if var.name == "CO" and unit is None and x.median() > 20:   # µg/m³ reported without a unit
            fn, desc = (lambda v: v / 1000), "values look like µg/m³ (median > 20): ÷ 1000"
            self.warnings.append(f"{header}: no unit given and values are too large for mg/m³; treated as µg/m³")
        m = {"source": header, "canonical": var.name, "unit_from": unit or f"{var.unit} (assumed)",
             "unit_to": var.unit, "conversion": desc, "by": how, "_fn": fn}
        self.mappings[key] = m
        return m

    def _ask_llm(self, header: str, series: pd.Series) -> dict | None:
        if not self.llm:
            return None
        if header in self._llm_cache:
            return self._llm_cache[header]
        schema = {"type": "object", "additionalProperties": False, "required": ["canonical", "unit", "reason"],
                  "properties": {"canonical": {"type": "string", "enum": S.CANONICAL + ["ignore"]},
                                 "unit": {"type": "string"}, "reason": {"type": "string"}}}
        canon = [{"name": v.name, "unit": v.unit, "kind": v.kind} for v in S.VARIABLES]
        ans = self.llm.ask(LLM_SYSTEM, json.dumps({"canonical_schema": canon, "column": header,
                                                   "statistics": _stats(series)}), schema)
        ok = (isinstance(ans, dict) and ans.get("canonical") in S.CANONICAL
              and S.converter(S.BY_NAME[ans["canonical"]], ans.get("unit")) is not None
              and not any(m["canonical"] == ans["canonical"] for m in self.mappings.values()))
        self._llm_cache[header] = ans if ok else None
        return self._llm_cache[header]

    def report(self) -> list[dict]:
        return [{k: v for k, v in m.items() if not k.startswith("_")} for m in self.mappings.values()]


def _wide(df: pd.DataFrame, skip: set[str], mapper: Mapper) -> pd.DataFrame:
    out = {}
    for col in df.columns:
        if col in skip:
            continue
        m = mapper.resolve_header(col, df[col])
        if m and m["canonical"] not in out:
            out[m["canonical"]] = m["_fn"](pd.to_numeric(df[col], errors="coerce"))
    return pd.DataFrame(out, index=df.index)


def _long(df: pd.DataFrame, param: str, value: str, unit: str | None, mapper: Mapper) -> pd.DataFrame:
    vals = pd.to_numeric(df[value], errors="coerce")
    out = pd.DataFrame(index=df.index)
    groups = df.groupby([df[param].astype(str), df[unit].astype(str) if unit else pd.Series("", index=df.index)])
    for (p, u), idx in groups.groups.items():
        m = mapper.resolve_header(p, vals.loc[idx], u or None)
        if m:
            out.loc[idx, m["canonical"]] = m["_fn"](vals.loc[idx]).to_numpy()
    return out


def adapt(path: str | Path, city: str | None = None, llm: LLM | None = None,
          log: Callable[[str], None] = print) -> tuple[pd.DataFrame, dict]:
    path = resolve(str(path))
    files = _files(path)
    if not files:
        raise NotAQData(f"no CSV, Parquet or Excel files under {path}")
    mapper = Mapper(llm)
    data, meta, skipped = [], [], []

    for f in files:
        df = _read(f)
        ts, ts_col = _timestamp(df)
        if ts is None:
            if _find(df, S.STATION_NAMES):
                meta.append((f, df))
            else:
                skipped.append({"file": f.name, "reason": "no timestamp or station column"})
            continue
        ts, tz_note = _to_local(ts)
        station, st_col = _station(df, f)
        param, value, unit = _find(df, S.PARAMETER_NAMES), _find(df, S.VALUE_NAMES), _find(df, S.UNIT_NAMES)
        skip = {c for c in df.columns if S.norm(c) in S.TIMESTAMP_NAMES or S.norm(c) in S.STATION_NAMES
                or c == st_col or S.norm(c) in ("lat", "lon", "latitude", "longitude", "city", "state", "sensorsid")}
        if param and value:
            layout, vals = "long", _long(df, param, value, unit, mapper)
        else:
            layout, vals = "wide", _wide(df, skip, mapper)
        vals.insert(0, "station", station.values)
        vals.insert(0, "timestamp", ts.values)
        vals = vals.dropna(subset=["timestamp"])
        data.append({"file": f.name, "layout": layout, "timestamp": ts_col, "station": st_col, "tz": tz_note,
                     "frame": vals, "family": tuple(sorted(df.columns))})

    if not data:
        raise NotAQData("no file has a usable timestamp column")

    # Files with the same columns are one table split across files; judge cadence per table.
    families: dict[tuple, list[dict]] = {}
    for d in data:
        families.setdefault(d["family"], []).append(d)
    order = ["subhourly", "hourly", "irregular", "daily", "unknown"]
    cadence = {fam: _granularity(pd.concat([d["frame"] for d in ds])) for fam, ds in families.items()}
    for fam, ds in families.items():
        log(f"{', '.join(d['file'] for d in ds[:3])}{' …' if len(ds) > 3 else ''}: {ds[0]['layout']} layout, "
            f"{sum(len(d['frame']) for d in ds):,} rows, {cadence[fam]}")
    # Several tables at different cadences (e.g. station_day + station_hour): keep the finest.
    finest = min(cadence.values(), key=order.index)
    for fam, ds in families.items():
        if cadence[fam] != finest:
            skipped += [{"file": d["file"], "reason": f"{cadence[fam]} data; a finer ({finest}) table is present"} for d in ds]
    for d in data:
        d["granularity"] = cadence[d["family"]]
    data = [d for d in data if d["granularity"] == finest]
    frame = pd.concat([d["frame"] for d in data], ignore_index=True)

    # Station metadata (names, city) from side tables keyed by the same station id.
    names, cities = {}, {}
    for f, m in meta:
        key = next((c for c in m.columns if "id" in S.norm(c) and S.norm(c) in S.STATION_NAMES), None)
        name = next((c for c in m.columns if S.norm(c) in ("stationname", "sitename", "name", "location")), None)
        cty = _find(m, ("city",))
        if key:
            ids = m[key].astype(str)
            if name:
                names.update(dict(zip(ids, m[name].astype(str))))
            if cty:
                cities.update(dict(zip(ids, m[cty].astype(str))))
    if city:
        keep = {s for s in frame["station"].unique()
                if cities.get(s, "").lower() == city.lower() or city.lower() in f"{s} {names.get(s, '')}".lower()}
        frame = frame[frame["station"].isin(keep)]
        if frame.empty:
            raise NotAQData(f"no station matches city '{city}'")

    def label(s: str) -> str:
        nm = names.get(s)
        return re.sub(r"[^A-Za-z0-9]+", "_", f"{s}_{nm}" if nm else s).strip("_")
    frame["station"] = frame["station"].map(label)

    # Granularity → hourly rows (daily data stays one row per day at 00:00).
    granularity = "daily" if finest == "daily" else "hourly"
    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.floor("D" if granularity == "daily" else "h")
    present = [c for c in S.CANONICAL if c in frame]
    frame = frame.groupby(["station", "timestamp"], as_index=False)[present].mean()

    # Plausibility: out-of-range values become missing.
    out_of_range = {}
    for c in present:
        v = S.BY_NAME[c]
        bad = frame[c].notna() & ~frame[c].between(v.lo, v.hi)
        if bad.any():
            out_of_range[c] = int(bad.sum())
            frame.loc[bad, c] = np.nan
    for c in S.CANONICAL:
        if c not in frame:
            frame[c] = np.nan
    frame = frame[S.COLUMNS]
    frame[S.CANONICAL] = frame[S.CANONICAL].astype("float32")

    pollutants = [c for c in present if S.BY_NAME[c].kind == "pollutant" and frame[c].notna().mean() > 0.05]
    if len(pollutants) < 3 or not {"PM2.5", "PM10"} & set(pollutants):
        raise NotAQData(f"only {pollutants} found; CPCB AQI needs at least three pollutants including PM2.5 or PM10")

    report = {
        "source": str(path), "files_used": [{k: d[k] for k in ("file", "layout", "timestamp", "station", "tz", "granularity")}
                                            for d in data],
        "files_skipped": skipped, "metadata_files": [f.name for f, _ in meta], "granularity": granularity,
        "source_granularity": finest, "city_filter": city, "stations": int(frame["station"].nunique()),
        "rows": len(frame), "start": str(frame["timestamp"].min()), "end": str(frame["timestamp"].max()),
        "mappings": mapper.report(), "ignored": [{"column": k, "reason": v} for k, v in mapper.ignored.items()],
        "missing_variables": [c for c in S.CANONICAL if c not in present],
        "out_of_range_set_missing": out_of_range,
        "coverage_pct": {c: round(float(frame[c].notna().mean() * 100), 1) for c in present},
        "warnings": mapper.warnings + (["no meteorology columns: the station_meteorology features will be empty"]
                                       if not any(S.BY_NAME[c].kind == "meteorology" for c in present) else []),
    }
    return frame, report


def suggest_settings(frame: pd.DataFrame, city: str | None) -> dict:
    """Years, split and coverage thresholds that fit this dataset's own time span."""
    days = frame.assign(d=frame.timestamp.dt.normalize(), y=frame.timestamp.dt.year)
    daily = days.groupby(["y"])["d"].nunique()
    full = [int(y) for y, n in daily.items() if n >= 300]
    if len(full) < 3:
        raise NotAQData(f"need at least three years with ≥300 days of data, found {full}")
    test = full[-1]
    n_val = 2 if len(full) >= 6 else 1
    val = full[-1 - n_val:-1]
    train = [y for y in full if y < val[0]]
    in_delhi = (city or "").lower() == "delhi"
    return {
        "years": [train[0], test],
        "split": {"train": [f"{train[0]}-01-01", f"{train[-1]}-12-31"], "val": [f"{val[0]}-01-01", f"{val[-1]}-12-31"],
                  "test": [f"{test}-01-01", f"{test}-12-31"]},
        "min_years_meeting_coverage": max(1, int(np.ceil(0.6 * (test - train[0] + 1)))),
        # ERA5 and CAMS features are fetched for Delhi's coordinates only.
        "groups": {"era5_blh": in_delhi, "cams_forecast": in_delhi},
    }


def run(state: dict, ledger: Ledger) -> dict:
    src = state["config"]["data"].get("source", {"format": "native"})
    fmt = src.get("format", "native")
    if fmt == "native":
        ledger.log("schema_adapter", "info", "Delhi CPCB station files: already in the canonical schema",
                   source={"format": "native", "path": state["config"]["data"]["cpcb_dir"]})
        return {"granularity": "hourly"}
    if fmt == "canonical":
        path = resolve(src["path"])
        rep_path = path.parent / "schema_report.json"
        report = json.loads(rep_path.read_text()) if rep_path.exists() else {}
        if report:
            ledger.artifact("schema_report.json").write_text(json.dumps(report, indent=2))
        ledger.log("schema_adapter", "info", f"using a dataset adapted earlier: {report.get('stations', '?')} stations, "
                   f"{report.get('granularity', 'hourly')}", source=src,
                   artifacts=["schema_report.json"] if report else [])
        return {"granularity": report.get("granularity", "hourly"),
                "paths": {**state.get("paths", {}), "canonical": str(path)}}

    llm = LLM(state["config"]["llm"], ledger)
    frame, report = adapt(src["path"], src.get("city"), llm, log=lambda m: ledger.log("schema_adapter", "info", m))
    out = ledger.dir / "canonical.parquet"
    frame.to_parquet(out, index=False)
    ledger.artifact("schema_report.json").write_text(json.dumps(report, indent=2))
    by = pd.Series([m["by"] for m in report["mappings"]]).value_counts().to_dict()
    ledger.log("schema_adapter", "info", f"mapped {len(report['mappings'])} columns ({by}) for {report['stations']} "
               f"stations, {report['granularity']}; ignored {len(report['ignored'])}",
               source=src, artifacts=["schema_report.json"], warnings=report["warnings"])
    return {"granularity": report["granularity"], "paths": {**state.get("paths", {}), "canonical": str(out)}}
