import { useEffect, useState } from "react";
import { api, usePolling, useResource } from "./api";
import { TopBar } from "./components/TopBar";
import { nodeStatus } from "./ledger";
import { useTheme } from "./theme";
import type { RunSummary } from "./types";
import { AgentsView } from "./views/AgentsView";
import { DataView } from "./views/DataView";
import { DriversView } from "./views/DriversView";
import { LedgerView } from "./views/LedgerView";
import { LoopView } from "./views/LoopView";
import { OverviewView } from "./views/OverviewView";
import { ReportView } from "./views/ReportView";
import { TestView } from "./views/TestView";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "agents", label: "Agent terminals" },
  { id: "data", label: "Data" },
  { id: "loop", label: "Training" },
  { id: "test", label: "Test year" },
  { id: "drivers", label: "Drivers" },
  { id: "ledger", label: "Ledger" },
  { id: "report", label: "Summary" },
] as const;
type Tab = (typeof TABS)[number]["id"];

const STATUS_PILL: Record<RunSummary["status"], string> = {
  running: "Running",
  done: "Finished",
  halted: "Stopped by guard",
  error: "Failed",
};

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const spec = useResource(api.spec, []);
  const [selected, setSelected] = useState<string | null>(() => decodeURIComponent(location.hash.slice(1)) || null);
  const runs = usePolling(api.runs, [], true, 3000);
  const run = runs?.find((r) => r.id === selected) ?? runs?.[0];
  const runId = run?.id ?? null;
  const events = usePolling(() => (runId ? api.events(runId) : Promise.resolve([])), [runId], run?.status === "running");
  const [tab, setTab] = useState<Tab>("overview");
  const [agent, setAgent] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setSelected(decodeURIComponent(location.hash.slice(1)) || null);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (runId) history.replaceState(null, "", `#${encodeURIComponent(runId)}`);
    setAgent(null);
  }, [runId]);

  const status = spec && events ? nodeStatus(spec, events) : null;
  const llmCalls = events?.filter((e) => e.status === "llm").length ?? 0;
  const openAgent = (node: string) => {
    setAgent(node);
    setTab("ledger");
  };

  return (
    <>
      <TopBar runs={runs} selected={runId} onSelect={setSelected} theme={theme} onTheme={toggleTheme} />
      <main className="main">
        {!run ? (
          <div className="empty" style={{ marginTop: 40 }}>
            {runs === undefined ? "Connecting to the pipeline API…" : "No runs yet. Start one with New run."}
          </div>
        ) : (
          <>
            <header className="head">
              <div>
                <p className="eyebrow">Next-day CPCB AQI category · {run.dataset}</p>
                <h1>Tomorrow's air, forecast today</h1>
              </div>
              <div className="run-tag">
                <span className={`pill ${run.status}`}>{STATUS_PILL[run.status]}</span>
                <span className="mono muted">{run.id}</span>
              </div>
            </header>
            {(run.status === "halted" || run.status === "error") && (
              <div className={`banner ${run.status}`} role="status">{run.reason}</div>
            )}

            <nav className="tabs" role="tablist">
              {TABS.map((t) => (
                <button key={t.id} role="tab" className="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                  {t.label}
                  {t.id === "agents" && llmCalls > 0 && <span className="count">{llmCalls} CLI</span>}
                </button>
              ))}
            </nav>

            {/* keyed on the theme so charts re-read their colours when it changes */}
            <div className="panel" role="tabpanel" key={theme}>
              {!events || !spec || !status ? <p className="muted">Loading the ledger…</p> : (
                <>
                  {tab === "overview" && <OverviewView run={run} events={events} status={status} onOpenAgent={openAgent} />}
                  {tab === "agents" && <AgentsView spec={spec} events={events} status={status} />}
                  {tab === "data" && <DataView runId={run.id} events={events} />}
                  {tab === "loop" && <LoopView events={events} />}
                  {tab === "test" && <TestView runId={run.id} events={events} />}
                  {tab === "drivers" && <DriversView runId={run.id} events={events} />}
                  {tab === "ledger" && <LedgerView events={events} spec={spec} agent={agent} onAgent={setAgent} />}
                  {tab === "report" && <ReportView runId={run.id} events={events} />}
                </>
              )}
            </div>
          </>
        )}
      </main>
    </>
  );
}
