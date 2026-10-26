import {
  ArrowDownRight, ArrowUpRight, Bot, Brain, CalendarDays, Gauge, Layers, ListTree, MapPin, SquareTerminal, Target, Workflow,
} from "lucide-react";
import { Architecture } from "../components/Architecture";
import { clock, humanName, reports, splitYears, type NodeStatus } from "../ledger";
import type { CriticDecision, LedgerEvent, RunSummary, Scores } from "../types";

function sourceLabel(run: RunSummary, events: LedgerEvent[]) {
  const adapter = reports(events, "schema_adapter")[0];
  const fmt = (adapter?.source as { format?: string } | undefined)?.format ?? "native";
  if (fmt === "native") return { title: "Delhi CPCB", sub: "Kaggle · hourly · native" };
  return { title: run.dataset, sub: fmt === "auto" ? "mapped in this run" : "adapted dataset" };
}

function Delta(props: { value: number; digits?: number; unit?: string }) {
  const up = props.value >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`delta ${up ? "up" : "down"}`}>
      <Icon aria-hidden="true" />
      {up ? "+" : "−"}{Math.abs(props.value).toFixed(props.digits ?? 3)}{props.unit ?? ""}
    </span>
  );
}

function Ring(props: { value: number; base: number }) {
  const r = 34, c = 2 * Math.PI * r;
  return (
    <svg width="92" height="92" viewBox="0 0 92 92" role="img"
      aria-label={`${Math.round(props.value * 100)}% of Very Poor and Severe days caught`}>
      <circle cx="46" cy="46" r={r} fill="none" stroke="var(--hover)" strokeWidth="9" />
      <circle cx="46" cy="46" r={r} fill="none" stroke="var(--faint)" strokeWidth="9" strokeOpacity="0.45"
        strokeDasharray={`${c * props.base} ${c}`} transform="rotate(-90 46 46)" strokeLinecap="round" />
      <circle cx="46" cy="46" r={r - 11} fill="none" stroke="var(--aqi-5)" strokeWidth="7"
        strokeDasharray={`${2 * Math.PI * (r - 11) * props.value} ${c}`} transform="rotate(-90 46 46)" strokeLinecap="round" />
    </svg>
  );
}

function Mini(props: { icon: typeof Gauge; value: string; label: string }) {
  const Icon = props.icon;
  return (
    <div className="tile span-3">
      <div className="mini">
        <div className="mini-icon"><Icon aria-hidden="true" /></div>
        <div><b>{props.value}</b><span>{props.label}</span></div>
      </div>
    </div>
  );
}

export function OverviewView(props: {
  run: RunSummary;
  events: LedgerEvent[];
  status: Record<string, NodeStatus>;
  onOpenAgent: (node: string) => void;
}) {
  const { events, status } = props;
  const years = splitYears(events);
  const tester = reports(events, "tester")[0];
  const results = tester?.results as Record<string, Scores> | undefined;
  const model = results && Object.keys(results).find((m) => m !== "persistence");
  const split = (reports(events, "splitter")[0]?.metrics as { sizes?: Record<string, number> } | undefined)?.sizes;
  const profile = reports(events, "profiler")[0]?.metrics as { stations_kept?: number } | undefined;
  const feats = reports(events, "features")[0]?.metrics as { features?: number } | undefined;
  const critic = reports(events, "critic").at(-1);
  const decision = critic?.decision as CriticDecision | undefined;
  const cliCalls = events.filter((e) => e.status === "llm").length;
  const recent = events.filter((e) => e.status === "info" || e.status === "halt" || e.status === "error").slice(-6).reverse();

  const states = Object.entries(status);
  const done = states.filter(([, s]) => s.state === "done").length;
  const running = states.find(([, s]) => s.state === "running")?.[0];
  const started = events[0]?.ts;
  const last = events.at(-1)?.ts;
  const elapsed = started && last ? Math.round((last - started) / 60) : null;
  const testLabel = years.test === "test year" ? "test year" : years.test;

  return (
    <div className="bento">
      {/* hero: the headline result */}
      <section className="tile span-4" aria-label="Test result">
        <div className="hero-glow" aria-hidden="true" />
        <div className="tile-label"><Target aria-hidden="true" />Locked {testLabel} test · macro-F1</div>
        {results && model ? (
          <>
            <div className="hero-num">{results[model].macro_f1.toFixed(3)}<small>{model}</small></div>
            <Delta value={results[model].macro_f1 - results.persistence.macro_f1} />
            <div className="tile-foot">vs <b>{results.persistence.macro_f1.toFixed(3)}</b> for "tomorrow = today" on {results[model].n?.toLocaleString()} station-days</div>
          </>
        ) : (
          <>
            <div className="hero-num" style={{ color: "var(--faint)" }}>—</div>
            <div className="tile-foot">Scored once, after the critic stops the training loop.</div>
          </>
        )}
      </section>

      {/* severe-day recall */}
      <section className="tile span-3" aria-label="Severe day recall">
        <div className="tile-label"><Gauge aria-hidden="true" />Very Poor / Severe days caught</div>
        {results && model ? (
          <div className="ring-wrap">
            <Ring value={results[model].severe_recall} base={results.persistence.severe_recall} />
            <div className="ring-text">
              <b>{Math.round(results[model].severe_recall * 100)}%</b>
              <span>persistence {Math.round(results.persistence.severe_recall * 100)}%</span>
              <div style={{ marginTop: 8 }}>
                <Delta value={(results[model].severe_recall - results.persistence.severe_recall) * 100} digits={1} unit=" pts" />
              </div>
            </div>
          </div>
        ) : <div className="tile-foot">Appears with the test result.</div>}
      </section>

      {/* pipeline progress */}
      <section className="tile span-5" aria-label="Pipeline progress">
        <div className="tile-label"><Workflow aria-hidden="true" />Pipeline</div>
        <div className="progress-track" role="img" aria-label={`${done} of ${states.length} agents done`}>
          {states.map(([name, s]) => <span key={name} className={s.state} title={`${humanName(name)}: ${s.state}`} />)}
        </div>
        <div className="progress-meta">
          <span><b>{done}</b> of {states.length} agents done{running ? <> · <b style={{ color: "var(--accent)" }}>{humanName(running)}</b> running</> : ""}</span>
          <span>{elapsed !== null ? <><b>{elapsed}</b> min</> : ""}{reports(events, "evaluator").length ? <> · <b>{reports(events, "evaluator").length}</b> training rounds</> : ""}</span>
        </div>
      </section>

      <Mini icon={MapPin} value={profile?.stations_kept ? String(profile.stations_kept) : "—"} label="stations kept" />
      <Mini icon={CalendarDays} value={split ? (split.train + split.val + split.test).toLocaleString() : "—"} label="station-days (train + val + test)" />
      <Mini icon={Layers} value={feats?.features ? String(feats.features) : "—"} label="leakage-checked features" />
      <Mini icon={SquareTerminal} value={String(cliCalls)} label="CLI calls by LLM agents" />

      <section className="tile span-12" aria-label="Architecture">
        <div className="surface-head row" style={{ marginBottom: 6 }}>
          <div>
            <h2><ListTree aria-hidden="true" />How the pipeline is built</h2>
            <p>Live status of every agent. Select one to read its ledger entries. ✦ marks agents that consult an LLM.</p>
          </div>
          <div className="legend" style={{ marginTop: 0 }}>
            {["pending", "running", "done", "halted"].map((s) => (
              <span key={s}><i className={`legend-swatch ${s}`} />{s === "halted" ? "halted / failed" : s}</span>
            ))}
          </div>
        </div>
        <Architecture status={status} source={sourceLabel(props.run, events)} onSelect={props.onOpenAgent} />
      </section>

      <section className="tile span-7" aria-label="Latest activity">
        <h2><Bot aria-hidden="true" />Latest activity</h2>
        {recent.length === 0 ? <p className="muted">Nothing recorded yet.</p> : (
          <ol className="activity" style={{ marginTop: 10 }}>
            {recent.map((e, i) => (
              <li key={`${e.ts}-${i}`}>
                <time>{clock(e.ts)}</time>
                <button className={`who ${e.status}`} onClick={() => props.onOpenAgent(e.node)}>{humanName(e.node)}</button>
                <span>{e.summary}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="tile span-5" aria-label="Latest critic decision">
        <h2><Brain aria-hidden="true" />Critic's latest call</h2>
        {decision ? (
          <div className="critic" style={{ marginTop: 12 }}>
            <div>After round {critic?.iteration as number}: <span className="action">{decision.action}</span></div>
            <p>{decision.diagnosis}</p>
            <p className="by">Decided by {decision.by}</p>
          </div>
        ) : <p className="muted" style={{ marginTop: 10 }}>The critic decides after the first training round.</p>}
      </section>
    </div>
  );
}
