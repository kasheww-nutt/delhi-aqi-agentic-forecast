import { useEffect, useRef, useState } from "react";
import { api, useResource } from "../api";
import { CATEGORIES, type DatasetConfig, type RunSummary } from "../types";

const STATUS_TEXT: Record<RunSummary["status"], string> = {
  running: "running",
  done: "finished",
  halted: "stopped by guard",
  error: "failed",
};

function runLabel(r: RunSummary) {
  const result = r.test ? `F1 ${r.test.macro_f1.toFixed(3)} vs ${r.test.persistence_f1.toFixed(3)}` : STATUS_TEXT[r.status];
  return `${r.id} · ${r.dataset} · ${result}`;
}

function datasetLabel(c: DatasetConfig) {
  if (!c.adapted) return `${c.name} · CPCB Kaggle, native`;
  return `${c.name} · ${c.adapted.stations} stations, ${c.adapted.start.slice(0, 4)}–${c.adapted.end.slice(0, 4)}`;
}

export function TopBar(props: {
  runs: RunSummary[] | undefined;
  selected: string | null;
  onSelect: (id: string) => void;
  theme: "dark" | "light";
  onTheme: () => void;
}) {
  const configs = useResource(api.configs, []);
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState("delhi");
  const [leaky, setLeaky] = useState(false);
  const [noLlm, setNoLlm] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pop = useRef<HTMLDivElement>(null);
  const current = props.runs?.find((r) => r.id === props.selected);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (pop.current && !pop.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    setTimeout(() => document.addEventListener("click", close));
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const { id } = await api.startRun({ config, leaky_demo: leaky, no_llm: noLlm });
      props.onSelect(id);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <>
      <div className="aqi-spine" aria-hidden="true">
        {CATEGORIES.map((_, i) => (
          <span key={i} style={{ background: `var(--aqi-${i})`, color: `var(--aqi-${i})` }} />
        ))}
      </div>
      <header className="topbar">
        <div className="brand">Delhi AQI <em>agents</em></div>
        {current && <span className={`dot ${current.status}`} aria-label={STATUS_TEXT[current.status]} />}
        <select className="select mono" aria-label="Run" value={props.selected ?? ""}
          onChange={(e) => props.onSelect(e.target.value)}>
          {props.runs === undefined && <option>Loading runs…</option>}
          {props.runs?.map((r) => <option key={r.id} value={r.id}>{runLabel(r)}</option>)}
        </select>
        <span className="spacer" />
        <button className="ghost" onClick={props.onTheme} aria-label="Switch colour theme">
          {props.theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <button className="btn" onClick={() => setOpen(!open)} aria-expanded={open}>New run</button>
        {open && (
          <div className="popover" ref={pop} role="dialog" aria-label="Start a new run">
            <h3>Start a new run</h3>
            <label className="field">
              <span>Dataset</span>
              <select value={config} onChange={(e) => setConfig(e.target.value)}>
                {(configs ?? [{ name: "delhi" } as DatasetConfig]).map((c) => (
                  <option key={c.name} value={c.name}>{c.project ? datasetLabel(c) : c.name}</option>
                ))}
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={leaky} onChange={(e) => setLeaky(e.target.checked)} />
              <span>Add a leaky feature (the guard should stop the run)</span>
            </label>
            <label className="check">
              <input type="checkbox" checked={noLlm} onChange={(e) => setNoLlm(e.target.checked)} />
              <span>Rule-based agents only (no CLI calls)</span>
            </label>
            <button className="btn" onClick={start} disabled={starting}>{starting ? "Starting…" : "Start run"}</button>
            {error && <span style={{ color: "var(--bad)", fontSize: 14 }}>{error}</span>}
          </div>
        )}
      </header>
    </>
  );
}
