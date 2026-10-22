import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { reports, splitYears } from "../ledger";
import type { CriticDecision, LedgerEvent, Scores } from "../types";

const MODEL_COLOUR: Record<string, string> = {
  persistence: "#5c6862",
  logreg: "#9cc64b",
  random_forest: "#ee8f34",
  lightgbm: "#1f5e63",
};

export function LoopView(props: { events: LedgerEvent[] }) {
  const evals = reports(props.events, "evaluator");
  const critics = reports(props.events, "critic");
  const years = splitYears(props.events);
  if (evals.length === 0) return <p className="empty">Training hasn't finished its first iteration yet.</p>;

  const models = Object.keys(evals[0].scores as Record<string, Scores>);
  const series = evals.map((e) => {
    const s = e.scores as Record<string, Scores>;
    return { iteration: e.iteration as number, ...Object.fromEntries(models.map((m) => [m, s[m].macro_f1])) };
  });
  const last = evals[evals.length - 1];
  const lastScores = last.scores as Record<string, Scores>;
  const best = models.filter((m) => m !== "persistence").sort((a, b) => lastScores[b].macro_f1 - lastScores[a].macro_f1)[0];

  return (
    <>
      <section className="card">
        <h2>Validation macro-F1 by iteration</h2>
        <p className="lede">
          Scored on {years.val} only. The critic sees these numbers; the {years.test} test year stays locked.
        </p>
        <div style={{ height: 260 }}>
          <ResponsiveContainer>
            <LineChart data={series} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="#c9cec6" strokeDasharray="2 4" />
              <XAxis dataKey="iteration" tick={{ fontSize: 12 }} allowDecimals={false} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number) => v.toFixed(3)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {models.map((m) => (
                <Line key={m} type="monotone" dataKey={m} stroke={MODEL_COLOUR[m] ?? "#1b2220"} strokeWidth={2}
                  strokeDasharray={m === "persistence" ? "5 4" : undefined} dot={{ r: 3 }} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="card">
        <h2>Latest iteration</h2>
        <p className="lede">Iteration {last.iteration as number}. A large gap between train and validation F1 means overfitting.</p>
        <table className="metrics">
          <thead>
            <tr><th>Model</th><th>Val macro-F1</th><th>Severe recall</th><th>Accuracy</th><th>Within ±1</th><th>Train macro-F1</th></tr>
          </thead>
          <tbody>
            {models.map((m) => {
              const s = lastScores[m];
              return (
                <tr key={m} className={m === best ? "best" : undefined}>
                  <td>{m}</td><td>{s.macro_f1.toFixed(3)}</td><td>{s.severe_recall.toFixed(3)}</td>
                  <td>{s.accuracy.toFixed(3)}</td><td>{s.within_one_category.toFixed(3)}</td>
                  <td>{s.train_macro_f1?.toFixed(3) ?? "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Critic decisions</h2>
        <p className="lede">One allowed action per iteration, or stop. Stopping rules are enforced in code.</p>
        {critics.length === 0 && <p className="muted">The critic hasn't decided yet.</p>}
        {critics.map((c) => {
          const d = c.decision as CriticDecision;
          return (
            <div className="critic" key={c.ts}>
              <div>
                After iteration {c.iteration as number}: <span className="action">{d.action}</span>{" "}
                <span className="by">· decided by {d.by}</span>
              </div>
              <p><b>Diagnosis.</b> {d.diagnosis}</p>
              <p><b>Rationale.</b> {d.rationale}</p>
            </div>
          );
        })}
      </section>
    </>
  );
}
