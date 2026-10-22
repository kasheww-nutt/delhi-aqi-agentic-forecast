import { clock, humanName } from "../ledger";
import type { LedgerEvent } from "../types";

export function LedgerFeed(props: { events: LedgerEvent[]; focus: string | null; onClear: () => void }) {
  const shown = props.events
    .filter((e) => (e.status === "info" || e.status === "halt" || e.status === "error") && e.node !== "pipeline")
    .filter((e) => !props.focus || e.node === props.focus)
    .reverse();
  return (
    <aside className="card feed" aria-label="Ledger">
      <h2>Ledger</h2>
      <p className="lede">
        {props.focus ? (
          <>
            Showing <b>{humanName(props.focus)}</b> only ·{" "}
            <button className="linkbtn" onClick={props.onClear}>show all agents</button>
          </>
        ) : (
          "Every agent's report, newest first. Select an agent to filter."
        )}
      </p>
      {shown.length === 0 ? (
        <p className="muted">Nothing recorded yet.</p>
      ) : (
        <ol>
          {shown.map((e, i) => (
            <li key={`${e.ts}-${i}`}>
              <time>{clock(e.ts)}</time>
              <div>
                <span className={`who ${e.status}`}>{humanName(e.node)}</span>{" "}
                <span>{e.summary}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
