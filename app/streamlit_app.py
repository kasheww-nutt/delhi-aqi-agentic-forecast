"""Pipeline dashboard. Reads only runs/<run_id>/ledger.jsonl and its artifacts.

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aqi.ledger import read_events  # noqa: E402
from aqi.spec import KIND, NODES  # noqa: E402

RUNS = ROOT / "runs"
CATS = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
COLOUR = {"pending": "#d9d9d9", "running": "#f6c344", "done": "#7cc47f", "halted": "#e06666", "error": "#e06666"}

st.set_page_config(page_title="Delhi AQI agentic pipeline", layout="wide")


def node_status(events: list[dict]) -> dict[str, dict]:
    status = {name: {"state": "pending", "seconds": None, "runs": 0} for name in NODES}
    for e in events:
        n = status.get(e["node"])
        if n is None:
            continue
        if e["status"] == "start":
            n["state"], n["runs"] = "running", n["runs"] + 1
        elif e["status"] in ("done", "halted", "error"):
            n["state"], n["seconds"] = e["status"], e.get("seconds")
    return status


def dag(status: dict) -> str:
    lines = ['digraph G { rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];']
    for name in NODES:
        s = status[name]
        extra = f"\\n{s['seconds']}s" if s["seconds"] is not None else ""
        extra += f"\\n×{s['runs']}" if s["runs"] > 1 else ""
        lines.append(f'{name} [label="{name}\\n({KIND[name]}){extra}", fillcolor="{COLOUR[s["state"]]}"];')
    for a, b in zip(NODES, NODES[1:]):
        lines.append(f"{a} -> {b};")
    lines.append('critic -> trainer [style=dashed, label="action", constraint=false];')
    lines.append('leakage_guard -> halt [style=dotted, label="leak"]; halt [shape=octagon, fillcolor="#f4cccc"];')
    return "\n".join(lines) + "}"


def runs() -> list[str]:
    found = [p for p in RUNS.glob("*") if (p / "ledger.jsonl").exists()]
    return [p.name for p in sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)]


with st.sidebar:
    st.header("Runs")
    with st.form("new_run"):
        leaky = st.checkbox("Leaky demo (guard should halt)")
        no_llm = st.checkbox("Rule-based critic only (no LLM)")
        if st.form_submit_button("Start new run"):
            run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-leaky" if leaky else "")
            cmd = [sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "--run-id", run_id]
            cmd += ["--leaky-demo"] if leaky else []
            cmd += ["--no-llm"] if no_llm else []
            subprocess.Popen(cmd, cwd=ROOT)
            st.session_state["run"] = run_id
    available = runs()
    if not available:
        st.info("No runs yet. Start one above, or run `python scripts/run_pipeline.py`.")
        st.stop()
    default = available.index(st.session_state["run"]) if st.session_state.get("run") in available else 0
    run_id = st.selectbox("Run", available, index=default)

run_dir = RUNS / run_id
art = run_dir / "artifacts"


@st.fragment(run_every=3)
def live():
    events = read_events(run_dir / "ledger.jsonl")
    end = next((e for e in reversed(events) if e["node"] == "pipeline" and e["status"] != "start"), None)
    errored = next((e for e in events if e["status"] == "error"), None)
    if errored:
        st.error(f"{errored['node']} failed: {errored['summary']}")
    elif end is None:
        st.info("Pipeline running…")
    elif end["status"] == "halted":
        st.error(f"Pipeline halted: {end['summary']}")
    else:
        st.success("Pipeline finished")
    st.graphviz_chart(dag(node_status(events)), use_container_width=True)
    log = pd.DataFrame([{"time": datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S"), "agent": e["node"],
                         "status": e["status"], "summary": e.get("summary", "")}
                        for e in events if e["status"] not in ("start",)])
    with st.expander("Ledger (latest first)", expanded=end is None):
        st.dataframe(log.iloc[::-1], hide_index=True, use_container_width=True)
    return events


st.title("Delhi next-day AQI — agentic pipeline")
st.caption(f"Run `{run_id}`")
events = live()


def info(node: str) -> list[dict]:
    return [e for e in events if e["node"] == node and e["status"] in ("info", "halt")]


t_data, t_loop, t_test, t_explain, t_report = st.tabs(
    ["Data & cleaning", "Training loop", "Locked test", "Explainability", "Report"])

with t_data:
    for e in info("cleaner"):
        st.subheader("Cleaner decisions")
        st.markdown("\n".join(f"- {d}" for d in e.get("decisions", [])))
    for e in info("leakage_guard"):
        (st.error if e["status"] == "halt" else st.success)(e["summary"])
        for p in e.get("problems", []):
            st.write("•", p)
    c1, c2 = st.columns(2)
    if (art / "coverage_heatmap.png").exists():
        c1.image(str(art / "coverage_heatmap.png"), caption="Profiler: PM2.5 coverage")
    if (art / "eda_overview.png").exists():
        c2.image(str(art / "eda_overview.png"), caption="EDA overview")
    if (art / "eda_notes.md").exists():
        st.markdown("**EDA agent notes (LLM, from summary statistics only)**")
        st.markdown((art / "eda_notes.md").read_text(encoding="utf-8"))

with t_loop:
    rows = []
    for e in info("evaluator"):
        for model, s in e["scores"].items():
            rows.append({"iteration": e["iteration"], "model": model, **s})
    if rows:
        df = pd.DataFrame(rows)
        st.plotly_chart(px.line(df, x="iteration", y="macro_f1", color="model", markers=True,
                                title="Validation macro-F1 per iteration"), use_container_width=True)
        st.dataframe(df, hide_index=True, use_container_width=True)
    for e in info("critic"):
        d = e["decision"]
        st.markdown(f"**Iteration {e['iteration']} → `{d['action']}`** ({d.get('by')})  \n"
                    f"*Diagnosis:* {d['diagnosis']}  \n*Rationale:* {d['rationale']}")

with t_test:
    for e in info("tester"):
        st.subheader(e["summary"])
        res = e["results"]
        st.dataframe(pd.DataFrame({m: {k: v for k, v in r.items() if k not in ("confusion", "per_class_recall")}
                                   for m, r in res.items()}).T, use_container_width=True)
        best = [m for m in res if m != "persistence"][0]
        cm = pd.DataFrame(res[best]["confusion"], index=CATS, columns=CATS)
        st.plotly_chart(px.imshow(cm, text_auto=True, color_continuous_scale="Blues",
                                  labels={"x": "predicted", "y": "actual"},
                                  title=f"{best} — 2025 confusion matrix"), use_container_width=True)

with t_explain:
    if (art / "shap_importance.png").exists():
        st.image(str(art / "shap_importance.png"))
    if (art / "explainer_notes.md").exists():
        st.markdown((art / "explainer_notes.md").read_text(encoding="utf-8"))

with t_report:
    if (art / "results_summary.md").exists():
        st.markdown((art / "results_summary.md").read_text(encoding="utf-8"))
