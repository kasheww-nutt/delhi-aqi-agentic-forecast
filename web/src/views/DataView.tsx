import ReactMarkdown from "react-markdown";
import { api, useResource } from "../api";
import { SchemaCard } from "../components/SchemaCard";
import { SupportedDataCard } from "../components/SupportedDataCard";
import { hasArtifact, reports } from "../ledger";
import type { LedgerEvent } from "../types";

export function DataView(props: { runId: string; events: LedgerEvent[] }) {
  const { runId, events } = props;
  const profiler = reports(events, "profiler")[0];
  const cleaner = reports(events, "cleaner")[0];
  const guard = reports(events, "leakage_guard")[0];
  const features = reports(events, "features")[0];
  const hasNotes = hasArtifact(events, "eda", "eda_notes.md");
  const notes = useResource(() => (hasNotes ? api.text(runId, "eda_notes.md") : Promise.resolve(null)), [runId, hasNotes]);

  if (!profiler) return <><SupportedDataCard /><p className="empty">The data agents haven't reported yet.</p></>;
  const problems = (guard?.problems as string[] | undefined) ?? [];
  const decisions = (cleaner?.decisions as string[] | undefined) ?? [];
  const skipped = (features?.skipped_groups as string[] | undefined) ?? [];
  // The agents log Python reprs; pull the names out so they read as chips, not code.
  const allowed = [...(guard?.summary ?? "").matchAll(/'([^']+)'/g)].map((m) => m[1]);
  const groups = [...(features?.summary ?? "").matchAll(/'([^']+)': (\d+)/g)].map((m) => [m[1], m[2]] as const);

  return (
    <>
      <SupportedDataCard />
      <SchemaCard runId={runId} events={events} />
      {guard && (
        <section className="card" style={{ borderLeft: `4px solid var(${guard.status === "halt" ? "--bad" : "--ok"})` }}>
          <h2>Leakage guard</h2>
          <p className="lede" style={{ marginBottom: 0 }}>
            {guard.status === "halt" ? guard.summary : (guard.summary ?? "").split(" (")[0] + "."}
          </p>
          {guard.status !== "halt" && allowed.length > 0 && (
            <>
              <p className="muted" style={{ margin: "12px 0 0", fontSize: 13.5 }}>
                Features about tomorrow that are allowed because they are known today:
              </p>
              <div className="chip-list">{allowed.map((f) => <span key={f}>{f}</span>)}</div>
            </>
          )}
          {problems.length > 0 && (
            <ul className="decisions">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}
        </section>
      )}

      {cleaner && (
        <section className="card">
          <h2>What the cleaner did</h2>
          <p className="lede">{cleaner.summary}</p>
          <ul className="decisions">{decisions.map((d) => <li key={d}>{d}</li>)}</ul>
          {features && (
            <>
              <p className="muted" style={{ margin: "16px 0 0", fontSize: 13.5 }}>
                {(features.summary ?? "").split("; groups")[0]}, by group
                {skipped.length > 0 && ` · skipped (no data yet): ${skipped.join(", ")}`}
              </p>
              <div className="chip-list">
                {groups.map(([g, n]) => <span key={g}>{g.replace(/_/g, " ")}<b>{n}</b></span>)}
              </div>
            </>
          )}
        </section>
      )}

      <div className="grid-2">
        <section className="card">
          <h2>Station coverage</h2>
          <p className="lede">{profiler.summary}</p>
          <img src={api.artifactUrl(runId, "coverage_heatmap.png")} alt="PM2.5 hourly coverage by station and year" />
        </section>
        <section className="card">
          <h2>Exploratory analysis</h2>
          <p className="lede">{reports(events, "eda")[0]?.summary ?? "Waiting for the EDA agent."}</p>
          <img src={api.artifactUrl(runId, "eda_overview.png")} alt="Missingness, seasonality, diurnal cycle and station medians" />
        </section>
      </div>

      {notes && (
        <section className="card md">
          <h2>EDA agent notes</h2>
          <p className="lede">Written by the LLM from summary statistics only.</p>
          <ReactMarkdown>{notes.content}</ReactMarkdown>
        </section>
      )}
    </>
  );
}
