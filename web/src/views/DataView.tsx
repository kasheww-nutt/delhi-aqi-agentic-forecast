import ReactMarkdown from "react-markdown";
import { api, useResource } from "../api";
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

  if (!profiler) return <p className="empty">The data agents haven't reported yet.</p>;
  const problems = (guard?.problems as string[] | undefined) ?? [];
  const decisions = (cleaner?.decisions as string[] | undefined) ?? [];
  const skipped = (features?.skipped_groups as string[] | undefined) ?? [];

  return (
    <>
      {guard && (
        <section className="card" style={{ borderLeft: `4px solid var(${guard.status === "halt" ? "--bad" : "--ok"})` }}>
          <h2>Leakage guard</h2>
          <p className="lede" style={{ marginBottom: problems.length ? 10 : 0 }}>{guard.summary}</p>
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
            <p className="muted" style={{ margin: "14px 0 0", fontSize: 13 }}>
              Features: {features.summary}
              {skipped.length > 0 && ` · skipped (no data yet): ${skipped.join(", ")}`}
            </p>
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
