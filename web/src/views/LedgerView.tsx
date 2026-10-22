import { useState } from "react";
import { clock, humanName } from "../ledger";
import type { LedgerEvent, SpecNode } from "../types";

function Details(props: { event: LedgerEvent }) {
  const { ts: _ts, node: _node, status: _status, summary: _summary, ...rest } = props.event;
  if (Object.keys(rest).length === 0) return null;
  return (
    <details className="raw">
      <summary>Recorded data</summary>
      <pre>{JSON.stringify(rest, null, 2)}</pre>
    </details>
  );
}

export function LedgerView(props: {
  events: LedgerEvent[];
  spec: SpecNode[];
  agent: string | null;
  onAgent: (node: string | null) => void;
}) {
  const [newestFirst, setNewestFirst] = useState(true);
  let shown = props.events.filter((e) => e.status === "info" || e.status === "halt" || e.status === "error");
  if (props.agent) shown = shown.filter((e) => e.node === props.agent);
  if (newestFirst) shown = [...shown].reverse();

  return (
    <section className="surface">
      <div className="surface-head row">
        <div>
          <h2>Ledger</h2>
          <p>Every report and decision, exactly as the agents wrote it.</p>
        </div>
        <div className="controls">
          <label>
            Agent{" "}
            <select value={props.agent ?? ""} onChange={(e) => props.onAgent(e.target.value || null)}>
              <option value="">All agents</option>
              {props.spec.map((n) => <option key={n.name} value={n.name}>{humanName(n.name)}</option>)}
            </select>
          </label>
          <button className="ghost" onClick={() => setNewestFirst(!newestFirst)}>
            {newestFirst ? "Newest first" : "Oldest first"}
          </button>
        </div>
      </div>
      {shown.length === 0 ? <p className="muted">No entries for this agent yet.</p> : (
        <ol className="activity full">
          {shown.map((e, i) => (
            <li key={`${e.ts}-${i}`}>
              <time>{clock(e.ts)}</time>
              <span className={`who ${e.status}`}>{humanName(e.node)}</span>
              <div>
                <span>{e.summary}</span>
                {Array.isArray(e.decisions) && (
                  <ul className="decisions">{(e.decisions as string[]).map((d) => <li key={d}>{d}</li>)}</ul>
                )}
                <Details event={e} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
