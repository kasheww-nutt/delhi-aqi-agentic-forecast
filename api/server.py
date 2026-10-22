"""HTTP API for the pipeline console. Reads runs/<id>/ledger.jsonl and artifacts; starts new runs.

    uvicorn api.server:app --port 8000          # API (+ serves web/dist when built)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
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
    out = {"id": d.name, "status": status, "started": events[0]["ts"] if events else None,
           "finished": end["ts"] if end else None, "reason": (error or end or {}).get("summary", "")}
    if tester:
        best = next(m for m in tester["results"] if m != "persistence")
        out["test"] = {"model": best, "macro_f1": tester["results"][best]["macro_f1"],
                       "persistence_f1": tester["results"]["persistence"]["macro_f1"]}
    return out


@app.get("/api/spec")
def spec():
    return [{"name": n, "kind": KIND[n]} for n in NODES]


@app.get("/api/runs")
def runs():
    found = [p for p in RUNS.glob("*") if (p / "ledger.jsonl").exists()] if RUNS.exists() else []
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


class NewRun(BaseModel):
    leaky_demo: bool = False
    no_llm: bool = False


@app.post("/api/runs")
def start_run(body: NewRun):
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-leaky" if body.leaky_demo else "")
    cmd = [sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "--run-id", run_id]
    cmd += ["--leaky-demo"] if body.leaky_demo else []
    cmd += ["--no-llm"] if body.no_llm else []
    subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"id": run_id}


DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
