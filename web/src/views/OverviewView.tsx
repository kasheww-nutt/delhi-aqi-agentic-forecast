import { Architecture } from "../components/Architecture";
import { clock, humanName, reports, splitYears, type NodeStatus } from "../ledger";
import type { LedgerEvent, RunSummary, Scores } from "../types";

function sourceLabel(run: RunSummary, events: LedgerEvent[]) {
  const adapter = reports(events, "schema_adapter")[0];
  const fmt = (adapter?.source as { format?: string } | undefined)?.format ?? "native";
  if (fmt === "native") return { title: "Delhi CPCB", sub: "Kaggle · hourly · native" };
  return { title: run.dataset, sub: fmt === "auto" ? "mapped in this run" : "adapted dataset" };
}

function Stat(props: { value: string; label: string; note?: string; tone?: "good" | "bad" }) {
  return (
    <div className="stat">
      <div className={`stat-value ${props.tone ?? ""}`}>{props.value}</div>
      <div className="stat-label">{props.label}</div>
      {props.note && <div className="stat-note">{props.note}</div>}
    </div>
  );
}

export function OverviewView(props: {
  run: RunSummary;
  events: LedgerEvent[];
  status: Record<string, NodeStatus> | null;
  onOpenAgent: (node: string) => void;
}) {
  const { events } = props;
  const split = reports(events, "splitter")[0]?.metrics as { sizes?: Record<string, number> } | undefined;
  const tester = reports(events, "tester")[0];
  const results = tester?.results as Record<string, Scores> | undefined;
  const model = results && Object.keys(results).find((m) => m !== "persistence");
  const iterations = reports(events, "evaluator").length;
  const years = splitYears(events);
  const recent = events.filter((e) => e.status === "info" || e.status === "halt" || e.status === "error").slice(-5).reverse();

  const f1 = model && results ? results[model].macro_f1 - results.persistence.macro_f1 : null;
  const sev = model && results ? results[model].severe_recall - results.persistence.severe_recall : null;
  const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(3)}`;

  return (
    <>
      <section className="stats">
        {results && model ? (
          <>
            <Stat value={results[model].macro_f1.toFixed(3)} label={`${years.test} macro-F1 · ${model}`}
              note={`${signed(f1!)} vs tomorrow = today`} tone={f1! > 0 ? "good" : "bad"} />
            <Stat value={results[model].severe_recall.toFixed(2)} label="Very Poor/Severe days caught"
              note={`${signed(sev!)} vs tomorrow = today`} tone={sev! > 0 ? "good" : "bad"} />
            <Stat value={`${(results[model].within_one_category * 100).toFixed(0)}%`} label="within one category" />
          </>
        ) : (
          <Stat value="—" label={years.test === "test year" ? "Test year" : `${years.test} test`}
            note="scored once, after the training loop stops" />
        )}
        <Stat value={String(iterations || "—")} label="training iterations" />
        {split?.sizes && (
          <Stat value={(split.sizes.train + split.sizes.val).toLocaleString()} label="station-days to learn from"
            note={`${split.sizes.test.toLocaleString()} locked for ${years.test}`} />
        )}
      </section>

      <section className="surface">
        <div className="surface-head">
          <h2>How the pipeline is built</h2>
          <p>Live status of every agent. Select an agent to read its ledger entries. ✦ marks the agents that consult Claude.</p>
        </div>
        <Architecture status={props.status} source={sourceLabel(props.run, events)} onSelect={props.onOpenAgent} />
        <div className="legend">
          {["pending", "running", "done", "halted"].map((s) => (
            <span key={s}><i className={`legend-swatch ${s}`} /> {s === "halted" ? "halted / failed" : s}</span>
          ))}
        </div>
      </section>

      <section className="surface">
        <div className="surface-head">
          <h2>Latest activity</h2>
        </div>
        {recent.length === 0 ? <p className="muted">Nothing recorded yet.</p> : (
          <ol className="activity">
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
    </>
  );
}
