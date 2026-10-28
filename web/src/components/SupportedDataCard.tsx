import { api, useResource } from "../api";

const UNIT: Record<string, string> = {
  "ug/m3": "µg/m³", "mg/m3": "mg/m³", "ng/m3": "ng/m³", degc: "°C", degC: "°C", degf: "°F", kelvin: "K",
  fraction: "0–1", "w/m2": "W/m²", "W/m2": "W/m²", mmhg: "mmHg", hpa: "hPa", kpa: "kPa", pa: "Pa", inhg: "inHg",
  deg: "°", in: "inch",
};
const unit = (u: string) => UNIT[u] ?? u;

/** What any dataset must look like for the schema adapter to accept it. Read live from src/aqi/schema.py. */
export function SupportedDataCard() {
  const s = useResource(() => api.schema(), []);
  if (!s) return null;
  const pollutants = s.variables.filter((v) => v.kind === "pollutant");
  return (
    <section className="card supported">
      <h2>What data the pipeline accepts</h2>
      <p className="lede">
        Any air-quality dataset can be used if it can be mapped onto this schema: one row per station per hour, with
        the variables below. The schema adapter does the mapping, and the Delhi CPCB data is already in this form.
      </p>

      <h3>Minimum to run</h3>
      <ul className="decisions">
        <li><b>A time column</b> (date and hour, or date only for daily data), plus a <b>station column</b> or one file per station.</li>
        <li><b>At least 3 pollutants, including PM2.5 or PM10.</b> The CPCB AQI cannot be calculated with fewer.</li>
        <li><b>At least 3 years with 300+ days each.</b> The last full year becomes the locked test, and the years before it train and validate.</li>
        <li>Weather columns are optional. Without them, the weather features are left empty and the run still works.</li>
      </ul>

      <h3>File and layout</h3>
      <ul className="decisions">
        <li>Formats: {s.formats.map((f) => <span key={f}><code>.{f}</code> </span>)}in one file or a whole folder.</li>
        <li>
          <b>Wide:</b> one column per variable (<code>Datetime, StationId, PM2.5, PM10, NO2 …</code>).{" "}
          <b>Long:</b> one row per reading, with a parameter, a value and optionally a unit column
          (<code>date, location, parameter=pm25, value=87, unit=µg/m³</code>).
        </li>
        <li>Hourly, sub-hourly (averaged to hourly) or daily. If a dataset has both, the finer table is used.</li>
        <li>Times are converted to {s.timezone}. Times with no zone are assumed to be local time, and that assumption is logged.</li>
      </ul>

      <h3>Variables</h3>
      <p className="muted small">
        Columns are matched by name, ignoring case, spaces and symbols, so <code>PM2.5 (µg/m³)</code> and{" "}
        <code>pm2_5</code> both become PM2.5. A unit in the header or in a unit column is converted. Values outside the
        plausible range become missing.
      </p>
      <div className="table-scroll">
        <table className="metrics">
          <thead>
            <tr>
              <th>Variable</th><th style={{ textAlign: "left" }}>Stored in</th><th style={{ textAlign: "left" }}>Also accepted</th>
              <th>Plausible range</th><th style={{ textAlign: "left" }}>Header names recognised</th>
            </tr>
          </thead>
          <tbody>
            {s.variables.map((v, i) => (
              <tr key={v.name} className={i === pollutants.length ? "group-start" : undefined}>
                <td>{v.name}<span className="muted kind">{v.kind === "pollutant" ? "pollutant" : "weather"}</span></td>
                <td style={{ textAlign: "left" }}>{unit(v.unit)}</td>
                <td style={{ textAlign: "left" }}>{v.accepts.filter((u) => unit(u) !== unit(v.unit)).map(unit).join(", ") || "–"}</td>
                <td>{v.range[0]} – {v.range[1]}</td>
                <td style={{ textAlign: "left", fontFamily: "var(--body)" }}>{v.aliases.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details className="raw">
        <summary>Column names recognised for time, station and long layouts · what is never imported</summary>
        <ul className="decisions">
          <li><b>Time:</b> {s.timestamp_names.join(", ")}. A separate <code>date</code> and <code>time</code> are joined.</li>
          <li><b>Station:</b> {s.station_names.join(", ")}. An id and a name are combined, and a stations side-table supplies names and city.</li>
          <li><b>Long layout:</b> parameter = {s.long_layout.parameter.join(" / ")}; value = {s.long_layout.value.join(" / ")}; unit = {s.long_layout.unit.join(" / ")}.</li>
          <li><b>Never imported:</b> the dataset's own AQI ({s.ignored_aqi.join(", ")}), because the pipeline recalculates AQI from the pollutants with CPCB rules. Also not imported: pollutants outside the schema ({s.ignored_extra.join(", ")}).</li>
          <li><b>Anything else</b> numeric that the rules cannot place is offered to the LLM. Its answer must name one of the variables above and a convertible unit, or the column is dropped.</li>
        </ul>
      </details>
    </section>
  );
}
