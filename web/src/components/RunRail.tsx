import { useState } from "react";
import { api } from "../api";
import { CATEGORIES, type RunSummary } from "../types";

const STATUS_TEXT: Record<RunSummary["status"], string> = {
  running: "Running",
  done: "Finished",
  halted: "Stopped by a guard",
  error: "Failed",
};

function describe(run: RunSummary) {
  if (run.test) return `Test macro-F1 ${run.test.macro_f1.toFixed(3)} · persistence ${run.test.persistence_f1.toFixed(3)}`;
  return STATUS_TEXT[run.status];
}

export function RunRail(props: {
  runs: RunSummary[] | undefined;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [leaky, setLeaky] = useState(false);
  const [noLlm, setNoLlm] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const { id } = await api.startRun({ leaky_demo: leaky, no_llm: noLlm });
      props.onSelect(id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <aside className="rail">
      <div>
        <div className="brand">
          Delhi next-day AQI
          <small>Agentic forecasting pipeline · CPCB stations 2018–2025</small>
        </div>
        <div className="band" aria-hidden="true">
          {CATEGORIES.map((_, i) => (
            <span key={i} style={{ background: `var(--aqi-${i})` }} />
          ))}
        </div>
      </div>

      <section>
        <p className="section-label">New run</p>
        <div className="new-run">
          <label className="check">
            <input type="checkbox" checked={leaky} onChange={(e) => setLeaky(e.target.checked)} />
            <span>Add a leaky feature (the guard should stop the run)</span>
          </label>
          <label className="check">
            <input type="checkbox" checked={noLlm} onChange={(e) => setNoLlm(e.target.checked)} />
            <span>Use the rule-based critic only</span>
          </label>
          <button className="btn" onClick={start} disabled={starting}>
            {starting ? "Starting…" : "Start run"}
          </button>
          {error && <span style={{ color: "var(--bad)", fontSize: 13 }}>{error}</span>}
        </div>
      </section>

      <section>
        <p className="section-label">Runs</p>
        {props.runs === undefined && <p className="muted">Loading runs…</p>}
        {props.runs?.length === 0 && <p className="muted">No runs yet. Start one above.</p>}
        <ul className="run-list">
          {props.runs?.map((r) => (
            <li key={r.id}>
              <button
                className="run-item"
                aria-current={r.id === props.selected}
                onClick={() => props.onSelect(r.id)}
              >
                <span className={`dot ${r.status}`} aria-label={STATUS_TEXT[r.status]} />
                <span className="id">{r.id}</span>
                <span className="meta">{describe(r)}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
