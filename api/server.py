"""HTTP API for the pipeline console. Reads runs/<id>/ledger.jsonl and artifacts; starts new runs.

    uvicorn api.server:app --port 8000          # API (+ serves web/dist when built)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aqi import schema as S  # noqa: E402
from aqi.agents.schema_adapter import READERS  # noqa: E402
from aqi.ledger import read_events  # noqa: E402
from aqi.spec import KIND, NODES  # noqa: E402

RUNS = ROOT / "runs"
app = FastAPI(title="Delhi AQI pipeline console")


def _run_dir(run_id: str) -> Path:
    d = (RUNS / run_id).resolve()
    if d.parent != RUNS.resolve() or not (d / "ledger.jsonl").exists():
        raise HTTPException(404, f"run {run_id} not found")
    return d


def _summary(d: Path) -> dict:
    events = read_events(d / "ledger.jsonl")
    end = next((e for e in reversed(events) if e["node"] == "pipeline" and e["status"] != "start"), None)
    error = next((e for e in events if e["status"] == "error"), None)
    tester = next((e for e in events if e["node"] == "tester" and e["status"] == "info"), None)
    status = "error" if error else "running" if end is None else end["status"]
    start = events[0] if events else {}
    cfg_name = re.search(r"configs[\\/]([\w\-]+)\.yaml", start.get("summary", ""))
    out = {"id": d.name, "status": status, "dataset": cfg_name.group(1) if cfg_name else "delhi",
           "started": events[0]["ts"] if events else None,
           "finished": end["ts"] if end else None, "reason": (error or end or {}).get("summary", "")}
    if tester:
        best = next(m for m in tester["results"] if m != "persistence")
        out["test"] = {"model": best, "macro_f1": tester["results"][best]["macro_f1"],
                       "persistence_f1": tester["results"]["persistence"]["macro_f1"]}
    return out


@app.get("/api/spec")
def spec():
    return [{"name": n, "kind": KIND[n]} for n in NODES]


# Units the adapter can be handed; each is offered only where schema.converter knows the conversion.
_UNITS = ["ug/m3", "mg/m3", "ng/m3", "ppb", "ppm", "degc", "degf", "kelvin", "%", "fraction", "m/s", "km/h",
          "knots", "mph", "deg", "mm", "cm", "in", "w/m2", "mmhg", "hpa", "kpa", "pa", "inhg"]


@app.get("/api/schema")
def schema():
    """What the schema adapter accepts, read from aqi.schema so the console always matches the rules."""
    return {
        "variables": [{"name": v.name, "unit": v.unit, "kind": v.kind, "range": [v.lo, v.hi], "aliases": list(v.aliases),
                       "accepts": [u for u in _UNITS if S.converter(v, u)]} for v in S.VARIABLES],
        "timezone": S.TIMEZONE,
        "timestamp_names": list(S.TIMESTAMP_NAMES), "station_names": list(S.STATION_NAMES),
        "long_layout": {"parameter": list(S.PARAMETER_NAMES), "value": list(S.VALUE_NAMES), "unit": list(S.UNIT_NAMES)},
        "ignored_aqi": list(S.IGNORE_AQI), "ignored_extra": list(S.IGNORE_EXTRA),
        "formats": sorted({s.lstrip(".") for s in READERS}),
    }


@app.get("/api/runs")
def runs():
    found = [p for p in RUNS.glob("*") if (p / "ledger.jsonl").exists() and not p.name.startswith("scout-")] if RUNS.exists() else []
    return [_summary(p) for p in sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)]


@app.get("/api/runs/{run_id}/events")
def events(run_id: str):
    return read_events(_run_dir(run_id) / "ledger.jsonl")


@app.get("/api/runs/{run_id}/artifacts/{name}")
def artifact(run_id: str, name: str):
    path = (_run_dir(run_id) / "artifacts" / name).resolve()
    if path.parent.name != "artifacts" or not path.exists():
        raise HTTPException(404, f"{name} not found in run {run_id}")
    return FileResponse(path)


@app.get("/api/runs/{run_id}/predictions")
def predictions(run_id: str):
    path = _run_dir(run_id) / "artifacts" / "test_predictions.csv"
    if not path.exists():
        raise HTTPException(404, "this run has no test predictions yet")
    p = pd.read_csv(path)
    out = {}
    for station, g in p.sort_values("target_date").groupby("station"):
        out[station] = {"dates": g["target_date"].tolist(), "actual": g["target"].astype(int).tolist(),
                        "predicted": g["pred"].astype(int).tolist(),
                        "persistence": g["persistence"].astype(int).tolist()}
    return out


@app.get("/api/runs/{run_id}/shap")
def shap(run_id: str):
    path = _run_dir(run_id) / "artifacts" / "shap_importance.csv"
    if not path.exists():
        raise HTTPException(404, "this run has no SHAP results")
    s = pd.read_csv(path, index_col=0).iloc[:, 0]
    return [{"feature": k, "importance": round(float(v), 4)} for k, v in s.head(20).items()]


@app.get("/api/runs/{run_id}/text/{name}")
def text(run_id: str, name: str):
    if not name.endswith((".md", ".json")):
        raise HTTPException(400, "only .md and .json artifacts can be read as text")
    path = _run_dir(run_id) / "artifacts" / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found in run {run_id}")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


@app.get("/api/configs")
def configs():
    """Datasets the pipeline can run on: the native Delhi config plus every adapted dataset."""
    out = []
    for p in sorted((ROOT / "configs").glob("*.yaml")):
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        src = cfg["data"].get("source", {"format": "native"})
        report = None
        if src.get("format") == "canonical":
            rp = ROOT / Path(src["path"]).parent / "schema_report.json"
            if rp.exists():
                r = json.loads(rp.read_text())
                report = {"stations": r["stations"], "granularity": r["granularity"], "city": r.get("city_filter"),
                          "start": r["start"][:10], "end": r["end"][:10]}
        out.append({"name": p.stem, "project": cfg.get("project"), "format": src.get("format", "native"),
                    "years": cfg["data"]["years"], "adapted": report})
    return out


class NewRun(BaseModel):
    config: str = "delhi"
    leaky_demo: bool = False
    no_llm: bool = False


@app.post("/api/runs")
def start_run(body: NewRun):
    cfg_path = ROOT / "configs" / f"{body.config}.yaml"
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", body.config) or not cfg_path.exists():
        raise HTTPException(404, f"no config named {body.config}")
    suffix = "" if body.config == "delhi" else f"-{body.config}"
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + suffix + ("-leaky" if body.leaky_demo else "")
    cmd = [sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "--run-id", run_id,
           "--config", f"configs/{body.config}.yaml"]
    cmd += ["--leaky-demo"] if body.leaky_demo else []
    cmd += ["--no-llm"] if body.no_llm else []
    subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"id": run_id}


@app.get("/api/scout/stations")
def scout_stations():
    daily = sorted((p for p in RUNS.glob("*") if (p / "daily.parquet").exists()), key=lambda p: p.stat().st_mtime)
    if not daily:
        return []
    names = pd.read_parquet(daily[-1] / "daily.parquet", columns=["station"])["station"].astype(str).unique()
    # "Anand_Vihar_Delhi_DPCC" -> "Anand Vihar": the scout geocodes the plain name
    return sorted({re.sub(r"^\d+\s+|\s*(Delhi|DPCC|CPCB|IMD|IITM)(\s|$).*", "", n.replace("_", " ")).strip() for n in names})


def _scout(d: Path) -> dict:
    events = read_events(d / "ledger.jsonl")
    info = next((e for e in events if e["node"] == "source_scout" and e["status"] == "info" and e.get("brief")), None)
    error = next((e for e in events if e["status"] == "error"), None)
    last = events[-1] if events else {}
    status = "error" if error else "done" if last.get("status") == "done" else "running"
    return {"id": d.name, "status": status, "station": events[0]["summary"].removeprefix("scouting ") if events else "",
            "started": events[0]["ts"] if events else None, "finished": last.get("ts") if status != "running" else None,
            "brief": info.get("brief") if info else None, "error": error["summary"] if error else None,
            "events": events}


@app.get("/api/scout")
def scouts():
    found = sorted(RUNS.glob("scout-*"), reverse=True) if RUNS.exists() else []  # ids are scout-<date>-<time>
    return [_scout(p) for p in found if (p / "ledger.jsonl").exists()][:20]


class NewScout(BaseModel):
    station: str


@app.post("/api/scout")
def start_scout(body: NewScout):
    station = body.station.strip()
    if not re.fullmatch(r"[A-Za-z0-9 .,'()\-]{2,60}", station):
        raise HTTPException(400, "station name should be plain text")
    run_id = "scout-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    subprocess.Popen([sys.executable, "-m", "aqi.scout", "--run-id", run_id, station], cwd=ROOT / "src",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"id": run_id}


DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
