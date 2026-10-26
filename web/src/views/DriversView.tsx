import ReactMarkdown from "react-markdown";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, useResource } from "../api";
import { hasArtifact, reports } from "../ledger";
import { cssVar } from "../theme";
import type { LedgerEvent } from "../types";

// Feature groups get their own hues; AQI hues stay reserved for categories.
const GROUP_COLOUR: [RegExp, string, string][] = [
  [/^cams_/, "#d16fa8", "CAMS forecast"],
  [/^(blh|ventilation)/, "#6c8ebf", "ERA5 boundary layer"],
  [/^city_|station_minus_city/, "#5b8def", "City context"],
  [/^(AT|RH|WS|WD|RF|SR|BP)_/, "#9b6bd6", "Station weather"],
  [/_t1$|^lockdown/, "#8894a8", "Calendar"],
  [/.*/, "--accent", "Pollutant history"],
];
const colourOf = (c: string) => (c.startsWith("--") ? cssVar(c) : c);
const groupOf = (f: string) => GROUP_COLOUR.find(([re]) => re.test(f))!;

export function DriversView(props: { runId: string; events: LedgerEvent[] }) {
  const done = !!reports(props.events, "explainer")[0];
  const shap = useResource(() => api.shap(props.runId), [props.runId, done]);
  const hasNotes = hasArtifact(props.events, "explainer", "explainer_notes.md");
  const notes = useResource(
    () => (hasNotes ? api.text(props.runId, "explainer_notes.md") : Promise.resolve(null)), [props.runId, hasNotes]);
  if (!done) return <p className="empty">Feature drivers appear after the final model is trained.</p>;
  if (!shap) return <p className="empty">This run's final model isn't a tree model, so SHAP was skipped.</p>;
  const data = shap.map((s) => ({ ...s, colour: colourOf(groupOf(s.feature)[1]) }));
  const groups = [...new Set(data.map((d) => groupOf(d.feature)[2]))];

  return (
    <>
      <section className="card">
        <h2>What drives tomorrow's category</h2>
        <p className="lede">Mean |SHAP| over 3,000 validation days, top 20 inputs, coloured by feature group.</p>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 14, marginBottom: 10, color: "var(--muted)" }}>
          {groups.map((g) => {
            const c = colourOf(GROUP_COLOUR.find(([, , name]) => name === g)![1]);
            return <span key={g}><span className="sw" style={{ background: c }} /> {g}</span>;
          })}
        </div>
        <div style={{ height: 26 * data.length + 40 }}>
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ left: 40, right: 20 }}>
              <XAxis type="number" tick={{ fontSize: 13, fill: cssVar("--muted") }} stroke={cssVar("--line-strong")} />
              <YAxis type="category" dataKey="feature" width={170} interval={0} stroke={cssVar("--line-strong")}
                tick={{ fontSize: 13, fontFamily: "Fira Code", fill: cssVar("--ink") }} />
              <Tooltip formatter={(v: number) => v.toFixed(4)} cursor={{ fill: "var(--hover)" }}
                contentStyle={{ background: "var(--panel-solid)", border: "1px solid var(--line-strong)", borderRadius: 10, color: "var(--ink)" }} />
              <Bar dataKey="importance" isAnimationActive={false}
                shape={(p: any) => <rect x={p.x} y={p.y + 2} width={p.width} height={p.height - 4} fill={p.payload.colour} rx={2} />} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      {notes && (
        <section className="card md">
          <h2>Explainer notes</h2>
          <ReactMarkdown>{notes.content}</ReactMarkdown>
        </section>
      )}
    </>
  );
}
