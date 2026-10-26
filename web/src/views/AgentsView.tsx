import { useEffect, useRef, useState } from "react";
import { clock, type NodeStatus } from "../ledger";
import type { LedgerEvent, SpecNode } from "../types";

const LLM_AGENTS = new Set(["schema_adapter", "eda", "critic", "explainer"]);
// Structured fields worth opening; everything else in an event is shown as text lines.
const DATA_KEYS = ["metrics", "scores", "decision", "results", "params", "overrides", "feature_groups", "source",
  "problems", "warnings", "skipped_groups", "traceback"];

function Json(props: { label: string; value: unknown }) {
  return (
    <details>
      <summary>{props.label}</summary>
      <pre>{typeof props.value === "string" ? props.value : JSON.stringify(props.value, null, 2)}</pre>
    </details>
  );
}

function Line(props: { ts?: number; tone?: string; children: React.ReactNode }) {
  return (
    <div className={`term-line ${props.tone ?? ""}`}>
      <time>{props.ts ? clock(props.ts) : ""}</time>
      <span>{props.children}</span>
    </div>
  );
}

function EventLines(props: { e: LedgerEvent }) {
  const e = props.e;
  if (e.status === "start") return <Line ts={e.ts} tone="dim">▶ started</Line>;
  if (e.status === "done") return <Line ts={e.ts} tone="ok">✓ done{typeof e.seconds === "number" ? ` in ${e.seconds}s` : ""}</Line>;
  if (e.status === "halted") return <Line ts={e.ts} tone="err">■ halted</Line>;
  if (e.status === "error") {
    return (
      <>
        <Line ts={e.ts} tone="err">✗ {e.summary}</Line>
        {e.traceback != null && <Json label="traceback" value={e.traceback} />}
      </>
    );
  }
  if (e.status === "llm") {
    const failed = Boolean(e.error);
    return (
      <>
        <Line ts={e.ts} tone="cmd">$ {String(e.command)}</Line>
        <div className="term-sub" style={{ color: "#7f8ba0" }}>
          {e.stdin ? "prompt on stdin" : "prompt as argument"} · {String(e.prompt ?? "").length.toLocaleString()} characters
        </div>
        <Json label="prompt sent" value={e.prompt} />
        {!failed && <Json label="reply" value={e.reply} />}
        <Line tone={failed ? "err" : "ok"}>{failed ? `✗ ${String(e.error)}` : `← ${e.summary}`}</Line>
      </>
    );
  }
  const decisions = Array.isArray(e.decisions) ? (e.decisions as string[]) : [];
  return (
    <>
      <Line ts={e.ts} tone={e.status === "halt" ? "err" : undefined}>{e.status === "halt" ? "■ " : ""}{e.summary}</Line>
      {decisions.length > 0 && <div className="term-sub"><ul>{decisions.map((d) => <li key={d}>{d}</li>)}</ul></div>}
      {typeof e.narrated_by === "string" && <div className="term-sub">narrated by: {e.narrated_by}</div>}
      {DATA_KEYS.filter((k) => k !== "traceback" && e[k] != null).map((k) => <Json key={k} label={k.replace("_", " ")} value={e[k]} />)}
    </>
  );
}

function Terminal(props: { node: SpecNode; status: NodeStatus; events: LedgerEvent[]; focus: boolean; onFocus: () => void }) {
  const body = useRef<HTMLDivElement>(null);
  const { state } = props.status;
  const calls = props.events.filter((e) => e.status === "llm");
  useEffect(() => {  // follow new output while the reader is at the bottom
    const el = body.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 80) el.scrollTop = el.scrollHeight;
  }, [props.events.length]);

  return (
    <section className={`term ${state}${props.focus ? " focus" : ""}`} aria-label={`${props.node.name} terminal`}>
      <div className="term-bar">
        <span className={`dot ${state}`} />
        <span className="name">{props.node.name}</span>
        <span className="kind">{props.node.kind}</span>
        <span className="meta">
          {calls.length > 0 && <span>{calls.length} CLI call{calls.length > 1 ? "s" : ""}</span>}
          {props.status.runs > 1 && <span>×{props.status.runs}</span>}
          {props.status.seconds != null && <span>{props.status.seconds}s</span>}
          <button onClick={props.onFocus}>{props.focus ? "shrink" : "expand"}</button>
        </span>
      </div>
      <div className="term-body" ref={body}>
        {props.events.length === 0 ? (
          <Line tone="dim">waiting for upstream agents…</Line>
        ) : (
          props.events.map((e, i) => <EventLines key={`${e.ts}-${i}`} e={e} />)
        )}
        {state === "running" && <Line><span className="cursor" /></Line>}
      </div>
    </section>
  );
}

export function AgentsView(props: { spec: SpecNode[]; events: LedgerEvent[]; status: Record<string, NodeStatus> }) {
  const [filter, setFilter] = useState<"all" | "llm" | "problems">("all");
  const [focus, setFocus] = useState<string | null>(null);
  const byAgent = (name: string) => props.events.filter((e) => e.node === name);
  const shown = props.spec.filter((n) => {
    if (filter === "llm") return LLM_AGENTS.has(n.name);
    if (filter === "problems") return byAgent(n.name).some((e) => e.status === "halt" || e.status === "error" || Boolean(e.error));
    return true;
  });
  const calls = props.events.filter((e) => e.status === "llm");

  return (
    <>
      <section className="surface-head row" style={{ marginBottom: 0 }}>
        <div>
          <h2 style={{ fontFamily: "var(--display)", fontStretch: "112%", fontSize: 22, margin: "0 0 6px" }}>Agent terminals</h2>
          <p className="muted" style={{ margin: 0, fontSize: 15 }}>
            Live output of every agent. LLM agents show the exact CLI command, the prompt they sent and the raw reply
            ({calls.length} CLI call{calls.length === 1 ? "" : "s"} in this run).
          </p>
        </div>
        <div className="chips" role="group" aria-label="Filter terminals">
          {([["all", "All agents"], ["llm", "LLM agents ✦"], ["problems", "Problems"]] as const).map(([id, label]) => (
            <button key={id} className="ghost" aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>
          ))}
        </div>
      </section>
      {shown.length === 0 ? <p className="empty">No agent matches this filter.</p> : (
        <div className="term-grid">
          {shown.map((n) => (
            <Terminal key={n.name} node={n} status={props.status[n.name]} events={byAgent(n.name)}
              focus={focus === n.name} onFocus={() => setFocus(focus === n.name ? null : n.name)} />
          ))}
        </div>
      )}
    </>
  );
}
