import { Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, useResource } from "../api";
import type { DatasetConfig } from "../types";

function datasetLabel(c: DatasetConfig) {
  if (!c.adapted) return `${c.name} — Delhi CPCB, native`;
  return `${c.name} — ${c.adapted.stations} stations, ${c.adapted.start.slice(0, 4)}–${c.adapted.end.slice(0, 4)}`;
}

export function NewRunDialog(props: { onClose: () => void; onStarted: (id: string) => void }) {
  const configs = useResource(api.configs, []);
  const [config, setConfig] = useState("delhi");
  const [leaky, setLeaky] = useState(false);
  const [noLlm, setNoLlm] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const first = useRef<HTMLSelectElement>(null);
  const onClose = useRef(props.onClose);
  onClose.current = props.onClose;

  useEffect(() => {  // focus the first field once; Escape closes
    first.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose.current();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, []);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const { id } = await api.startRun({ config, leaky_demo: leaky, no_llm: noLlm });
      props.onStarted(id);
    } catch (e) {
      setError(`${(e as Error).message}. Check that the API server is running, then try again.`);
      setStarting(false);
    }
  }

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="new-run-title">
        <h3 id="new-run-title">Start a new run</h3>
        <p>Runs the full 14-agent pipeline. Takes about 5 minutes; you can watch it live.</p>
        <label className="field">
          Dataset
          <select ref={first} value={config} onChange={(e) => setConfig(e.target.value)}>
            {(configs ?? [{ name: "delhi" } as DatasetConfig]).map((c) => (
              <option key={c.name} value={c.name}>{c.project ? datasetLabel(c) : c.name}</option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={leaky} onChange={(e) => setLeaky(e.target.checked)} />
          <span>Leakage demo<small>Adds tomorrow's PM2.5 as a feature; the guard should stop the run.</small></span>
        </label>
        <label className="check">
          <input type="checkbox" checked={noLlm} onChange={(e) => setNoLlm(e.target.checked)} />
          <span>Rules only<small>Skip the CLI calls; the critic and notes use rule-based fallbacks.</small></span>
        </label>
        {error && <span role="alert" style={{ color: "var(--bad)", fontSize: 14 }}>{error}</span>}
        <div className="actions">
          <button className="ghost" onClick={props.onClose}>Cancel</button>
          <button className="btn" onClick={start} disabled={starting}><Play aria-hidden="true" />{starting ? "Starting…" : "Start run"}</button>
        </div>
      </div>
    </div>
  );
}
