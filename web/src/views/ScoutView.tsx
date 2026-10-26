import { Radar } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, usePolling, useResource } from "../api";
import { clock } from "../ledger";
import { EventLines } from "./AgentsView";

const TOOLS = [
  ["station_snapshot", "latest AQI at the station (pipeline data)"],
  ["fires", "crop fires in Punjab–Haryana (NASA FIRMS satellites)"],
  ["nearby_sources", "construction, industry, landfills and big roads within 2 km (OpenStreetMap)"],
  ["web search", "this week's news: GRAP stage, demolition, waste fires"],
];

export function ScoutView() {
  const stations = useResource(() => api.scoutStations(), []);
  const [station, setStation] = useState("Anand Vihar");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pick, setPick] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const scouts = usePolling(() => api.scouts(), [tick], true, 3000);
  const running = scouts?.some((s) => s.status === "running") ?? false;
  const shown = scouts?.find((s) => s.id === pick) ?? scouts?.[0];

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const { id } = await api.startScout(station);
      setPick(id);
      setTick((t) => t + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="scout">
      <section className="card">
        <h2>Scout a station</h2>
        <p className="lede">
          An LLM agent (Claude Code CLI) calls our own MCP tools and web search, then writes a short, sourced brief.
          It explains the present only and never feeds the forecasting model, since live pages would leak hindsight.
        </p>
        <div className="scout-form">
          <label className="field">
            Station
            <select value={station} onChange={(e) => setStation(e.target.value)}>
              {(stations ?? [station]).map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <button className="btn" onClick={start} disabled={busy || running}>
            <Radar aria-hidden="true" />{running ? "Scouting…" : "Run scout"}
          </button>
        </div>
        {error && <p className="err-text">{error}</p>}
        <div className="chip-list" aria-label="Tools the scout can call">
          {TOOLS.map(([name, what]) => <span key={name} title={what}>{name}</span>)}
        </div>
        <p className="muted small">A scout takes one to five minutes: each tool call goes to a live public service.</p>
      </section>

      {scouts && scouts.length > 0 && (
        <div className="scout-body">
          <nav className="scout-list" aria-label="Past scouts">
            {scouts.map((s) => (
              <button key={s.id} className={s.id === shown?.id ? "on" : ""} onClick={() => setPick(s.id)}>
                <span className={`dot ${s.status}`} />
                <span>{s.station}</span>
                <time>{s.started ? clock(s.started) : ""}</time>
              </button>
            ))}
          </nav>
          {shown && (
            <div className="scout-main">
              <section className="card md">
                {shown.brief ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{shown.brief}</ReactMarkdown>
                ) : shown.status === "running" ? (
                  <p className="muted">The scout is calling its tools for {shown.station}…</p>
                ) : (
                  <p className="err-text">{shown.error ?? "No brief was written."}</p>
                )}
              </section>
              <section className={`term ${shown.status === "running" ? "running" : shown.status}`} aria-label="Scout terminal">
                <div className="term-bar">
                  <span className={`dot ${shown.status}`} />
                  <span className="name">source_scout</span>
                  <span className="kind">llm + mcp</span>
                </div>
                <div className="term-body">
                  {shown.events.map((e, i) => <EventLines key={`${e.ts}-${i}`} e={e} />)}
                  {shown.status === "running" && <div className="term-line"><time /><span><span className="cursor" /></span></div>}
                </div>
              </section>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
