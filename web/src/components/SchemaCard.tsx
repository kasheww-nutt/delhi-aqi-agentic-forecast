import { api, useResource } from "../api";
import { hasArtifact, reports } from "../ledger";
import type { LedgerEvent, SchemaReport } from "../types";

/** What the schema adapter did to bring this run's dataset into the canonical schema. */
export function SchemaCard(props: { runId: string; events: LedgerEvent[] }) {
  const adapter = reports(props.events, "schema_adapter")[0];
  const has = hasArtifact(props.events, "schema_adapter", "schema_report.json");
  const raw = useResource(() => (has ? api.text(props.runId, "schema_report.json") : Promise.resolve(null)), [props.runId, has]);
  if (!adapter) return null;
  if (!has) {
    return (
      <section className="card">
        <h2>Schema</h2>
        <p className="lede" style={{ marginBottom: 0 }}>{adapter.summary}</p>
      </section>
    );
  }
  if (!raw) return null;
  const r = JSON.parse(raw.content) as SchemaReport;
  const files = r.files_used.map((f) => f.file);
  return (
    <section className="card">
      <h2>How this dataset was mapped</h2>
      <p className="lede">
        {r.stations} stations{r.city_filter ? ` in ${r.city_filter}` : ""} · {r.rows.toLocaleString()} {r.granularity} rows ·{" "}
        {r.start.slice(0, 10)} → {r.end.slice(0, 10)} · from {files.slice(0, 2).join(", ")}
        {files.length > 2 ? ` and ${files.length - 2} more` : ""}
      </p>
      <table className="metrics">
        <thead>
          <tr><th>Source column</th><th style={{ textAlign: "left" }}>Canonical</th><th style={{ textAlign: "left" }}>Unit</th>
            <th style={{ textAlign: "left" }}>Conversion</th><th>Matched by</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {r.mappings.map((m) => (
            <tr key={m.source}>
              <td>{m.source}</td>
              <td style={{ textAlign: "left" }}>{m.canonical}</td>
              <td style={{ textAlign: "left" }}>{m.unit_from} → {m.unit_to}</td>
              <td style={{ textAlign: "left", fontFamily: "var(--body)" }}>{m.conversion}</td>
              <td>{m.by === "llm" ? "Claude ✦" : m.by}</td>
              <td>{r.coverage_pct[m.canonical]?.toFixed(0) ?? "–"}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {(r.ignored.length > 0 || r.files_skipped.length > 0 || r.warnings.length > 0) && (
        <ul className="decisions" style={{ marginTop: 16 }}>
          {r.ignored.map((i) => <li key={i.column}><b>{i.column}</b> not imported: {i.reason}</li>)}
          {r.files_skipped.map((f) => <li key={f.file}><b>{f.file}</b> skipped: {f.reason}</li>)}
          {r.warnings.map((w) => <li key={w}>{w}</li>)}
          {r.missing_variables.length > 0 && <li>Not in this dataset: {r.missing_variables.join(", ")}</li>}
        </ul>
      )}
    </section>
  );
}
