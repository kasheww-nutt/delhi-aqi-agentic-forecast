import { useMemo, useState } from "react";
import { api, useResource } from "../api";
import { reports, splitYears } from "../ledger";
import { CATEGORIES, type LedgerEvent, type Scores, type StationForecast } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function dayOfYear(iso: string) {
  const d = new Date(iso.slice(0, 10) + "T00:00:00Z");
  return Math.floor((d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 1)) / 86400000) + 1;
}

function stationLabel(id: string) {
  return id.replace(/^\d+_/, "").replace(/_Delhi.*$/, "").replace(/_/g, " ");
}

/** Signature view: one tick per day of the test year, actual vs forecast, in CPCB category colours. */
function ForecastStrip(props: { data: Record<string, StationForecast>; model: string; year: string }) {
  const stations = useMemo(() => Object.keys(props.data).sort((a, b) => stationLabel(a).localeCompare(stationLabel(b))), [props.data]);
  const [station, setStation] = useState(() => stations.find((s) => s.includes("Anand_Vihar")) ?? stations[0]);
  const [against, setAgainst] = useState<"predicted" | "persistence">("predicted");
  const f = props.data[station];
  if (!f) return null;
  const forecast = f[against];
  const days = f.dates.map(dayOfYear);
  const exact = forecast.filter((p, i) => p === f.actual[i]).length;
  const within = forecast.filter((p, i) => Math.abs(p - f.actual[i]) <= 1).length;
  const severeDays = f.actual.filter((a) => a >= 4).length;
  const severeCaught = f.actual.filter((a, i) => a >= 4 && forecast[i] >= 4).length;

  const row = (values: number[], label: string, cls = "") => (
    <>
      <span className="row-label">{label}</span>
      <div className={`ticks ${cls}`} style={{ gridTemplateColumns: "repeat(366, minmax(0, 1fr))" }}>
        {values.map((v, i) =>
          cls === "hits" ? (
            <span key={i} className={v ? "miss" : ""} style={{ gridColumn: days[i] }} />
          ) : (
            <span key={i} style={{ gridColumn: days[i], background: `var(--aqi-${v})` }}
              title={`${f.dates[i].slice(0, 10)} · ${label}: ${CATEGORIES[v]}`} />
          ),
        )}
      </div>
    </>
  );

  return (
    <section className="card">
      <h2>{props.year}, day by day</h2>
      <p className="lede">
        Each tick is one day of the locked test year at one station: the category that happened, and the one forecast
        the evening before. Black marks underneath are misses.
      </p>
      <div className="strip-controls">
        <label>
          Station{" "}
          <select value={station} onChange={(e) => setStation(e.target.value)}>
            {stations.map((s) => <option key={s} value={s}>{stationLabel(s)}</option>)}
          </select>
        </label>
        <label>
          Forecast by{" "}
          <select value={against} onChange={(e) => setAgainst(e.target.value as "predicted" | "persistence")}>
            <option value="predicted">{props.model}</option>
            <option value="persistence">persistence (tomorrow = today)</option>
          </select>
        </label>
      </div>
      <div className="strip">
        {row(f.actual, "Actual")}
        {row(forecast, "Forecast")}
        {row(forecast.map((p, i) => (p === f.actual[i] ? 0 : 1)), "Miss", "hits")}
        <span />
        <div className="months">{MONTHS.map((m) => <span key={m}>{m}</span>)}</div>
      </div>
      <div className="strip-stats">
        <span>Exact category <b>{((100 * exact) / forecast.length).toFixed(0)}%</b></span>
        <span>Within one category <b>{((100 * within) / forecast.length).toFixed(0)}%</b></span>
        <span>Very Poor/Severe days caught <b>{severeCaught}/{severeDays}</b></span>
        <span className="muted">{forecast.length} days with a forecast</span>
      </div>
    </section>
  );
}

function Confusion(props: { matrix: number[][]; model: string }) {
  return (
    <section className="card">
      <h2>Where the forecast lands</h2>
      <p className="lede">Rows are what happened, columns what {props.model} forecast. Shading is the share of each row.</p>
      <div className="cm" role="table" aria-label="Confusion matrix">
        <span />
        {CATEGORIES.map((c, j) => (
          <span key={c} className="h"><span className="sw" style={{ background: `var(--aqi-${j})` }} /> {c}</span>
        ))}
        {props.matrix.map((row, i) => {
          const total = row.reduce((a, b) => a + b, 0) || 1;
          return [
            <span key={`r${i}`} className="rh">{CATEGORIES[i]} <span className="sw" style={{ background: `var(--aqi-${i})` }} /></span>,
            ...row.map((v, j) => {
              const share = v / total;
              return (
                <span key={`${i}-${j}`} className={`cell${i === j ? " diag" : ""}`}
                  style={{ background: `color-mix(in srgb, var(--accent) ${Math.round(6 + share * 80)}%, transparent)`,
                    color: share > 0.45 ? "#fff" : "inherit", fontWeight: share > 0.45 ? 600 : 400 }}
                  title={`${CATEGORIES[i]} → ${CATEGORIES[j]}: ${v} (${(share * 100).toFixed(0)}%)`}>
                  {v}
                </span>
              );
            }),
          ];
        })}
      </div>
    </section>
  );
}

export function TestView(props: { runId: string; events: LedgerEvent[] }) {
  const tester = reports(props.events, "tester")[0];
  const preds = useResource(() => api.predictions(props.runId), [props.runId, !!tester]);
  const year = splitYears(props.events).test;
  if (!tester) return <p className="empty">The {year} test year is still locked. The tester runs once, after the critic stops the loop.</p>;
  const results = tester.results as Record<string, Scores>;
  const model = Object.keys(results).find((m) => m !== "persistence")!;
  const rows: [string, keyof Scores, boolean][] = [
    ["Macro-F1", "macro_f1", true], ["Very Poor/Severe recall", "severe_recall", true],
    ["Accuracy", "accuracy", true], ["Within one category", "within_one_category", true],
    ["Mean category error", "mean_category_error", false],
  ];
  return (
    <>
      <section className="card">
        <h2>Locked test, scored once</h2>
        <p className="lede">{tester.summary}</p>
        <table className="metrics">
          <thead><tr><th>Metric ({year})</th><th>{model}</th><th>persistence</th><th>Difference</th></tr></thead>
          <tbody>
            {rows.map(([label, key, higherIsBetter]) => {
              const a = results[model][key] as number, b = results.persistence[key] as number;
              const better = higherIsBetter ? a > b : a < b;
              return (
                <tr key={key}>
                  <td>{label}</td><td>{a.toFixed(3)}</td><td>{b.toFixed(3)}</td>
                  <td style={{ color: a === b ? "inherit" : better ? "var(--ok)" : "var(--bad)" }}>
                    {(a - b >= 0 ? "+" : "") + (a - b).toFixed(3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      {preds === undefined && <p className="muted">Loading forecasts…</p>}
      {preds && <ForecastStrip data={preds} model={model} year={year} />}
      <Confusion matrix={results[model].confusion!} model={model} />
    </>
  );
}
