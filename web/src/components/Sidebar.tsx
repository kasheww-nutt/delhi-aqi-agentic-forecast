import {
  Activity, BarChart3, Database, FileText, FlaskConical, LayoutDashboard, ScrollText, SquareTerminal,
  type LucideIcon,
} from "lucide-react";
import { CATEGORIES, type RunSummary } from "../types";

export type Page = "overview" | "agents" | "data" | "loop" | "test" | "drivers" | "ledger" | "report";

export const PAGES: { id: Page; label: string; icon: LucideIcon; blurb: string }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, blurb: "Headline results and the live state of every agent." },
  { id: "agents", label: "Agent terminals", icon: SquareTerminal, blurb: "Each agent's live output, including the exact CLI calls the LLM agents make." },
  { id: "data", label: "Data", icon: Database, blurb: "How the dataset was mapped, cleaned and checked for leakage." },
  { id: "loop", label: "Training loop", icon: Activity, blurb: "Validation scores per round and the critic's reasoning." },
  { id: "test", label: "Test year", icon: FlaskConical, blurb: "The locked test year, scored once, day by day." },
  { id: "drivers", label: "Drivers", icon: BarChart3, blurb: "What the final model relies on to forecast tomorrow." },
  { id: "ledger", label: "Ledger", icon: ScrollText, blurb: "Every report and decision, exactly as the agents wrote it." },
  { id: "report", label: "Summary", icon: FileText, blurb: "Results tables ready for the report." },
];

const STATUS: Record<RunSummary["status"], string> = { running: "running", done: "finished", halted: "stopped by guard", error: "failed" };

export function Sidebar(props: {
  page: Page;
  onPage: (p: Page) => void;
  runs: RunSummary[] | undefined;
  selected: string | null;
  onSelect: (id: string) => void;
  cliCalls: number;
}) {
  return (
    <aside className="sidebar" aria-label="Navigation">
      <div className="logo">
        <div className="logo-mark" aria-hidden="true"><span>A</span></div>
        <div>
          <b>Delhi AQI agents</b>
          <small>Next-day air-quality forecasting</small>
        </div>
      </div>

      <nav>
        <p className="nav-label">Workspace</p>
        <div className="nav">
          {PAGES.map(({ id, label, icon: Icon }) => (
            <button key={id} aria-current={props.page === id ? "page" : undefined} onClick={() => props.onPage(id)}>
              <Icon aria-hidden="true" />
              <span>{label}</span>
              {id === "agents" && props.cliCalls > 0 && <span className="badge">{props.cliCalls} CLI</span>}
            </button>
          ))}
        </div>
      </nav>

      <section>
        <p className="nav-label">Recent runs</p>
        <div className="recent">
          {props.runs?.slice(0, 6).map((r) => (
            <button key={r.id} aria-current={r.id === props.selected} onClick={() => props.onSelect(r.id)}>
              <span className={`dot ${r.status}`} aria-label={STATUS[r.status]} />
              <span className="rid">{r.id}</span>
              <span className="rmeta">
                {r.dataset} · {r.test ? `F1 ${r.test.macro_f1.toFixed(3)}` : STATUS[r.status]}
              </span>
            </button>
          ))}
          {props.runs?.length === 0 && <p className="muted" style={{ padding: "0 10px", fontSize: 13 }}>No runs yet.</p>}
        </div>
      </section>

      <div className="sidebar-foot" aria-label="AQI category colours">
        <div className="aqi-key">
          {CATEGORIES.map((c, i) => <span key={c} title={c} style={{ background: `var(--aqi-${i})` }} />)}
        </div>
        <div className="aqi-key-labels"><span>Good</span><span>Severe</span></div>
      </div>
    </aside>
  );
}
