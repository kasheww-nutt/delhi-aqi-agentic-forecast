import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, usePolling, useResource } from "./api";
import { Header } from "./components/Header";
import { PAGES, Sidebar, type Page } from "./components/Sidebar";
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

const STATUS: Record<RunSummary["status"], string> = {
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
  const [page, setPage] = useState<Page>("overview");
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

  useEffect(() => {
    window.scrollTo({ top: 0 }); // braces: newer browsers return a Promise here, which must not become the cleanup
  }, [page]);

  const status = spec && events ? nodeStatus(spec, events) : null;
  const cliCalls = events?.filter((e) => e.status === "llm").length ?? 0;
  const meta = PAGES.find((p) => p.id === page)!;
  const openAgent = (node: string) => {
    setAgent(node);
    setPage("ledger");
  };

  return (
    <div className="app">
      <Sidebar page={page} onPage={setPage} runs={runs} selected={runId} onSelect={setSelected} cliCalls={cliCalls} />
      <div className="content">
        <Header pageLabel={meta.label} runs={runs} selected={runId} onSelect={setSelected} theme={theme} onTheme={toggleTheme} />
        <main className="page" id="main">
          {!run ? (
            <div className="empty">
              {runs === undefined ? "Connecting to the pipeline API…" : "No runs yet. Start one with New run."}
            </div>
          ) : (
            <>
              <div className="page-head">
                <div>
                  <h1>{meta.label}</h1>
                  <p>{meta.blurb}</p>
                </div>
                <span className={`status-chip ${run.status}`}>
                  <span className={`dot ${run.status}`} />{STATUS[run.status]}<span className="muted">·</span><span className="mono">{run.dataset}</span>
                </span>
              </div>
              {(run.status === "halted" || run.status === "error") && (
                <div className="banner" role="status"><AlertTriangle aria-hidden="true" />{run.reason}</div>
              )}
              {/* keyed on page + theme: charts re-read their colours, and each page animates in */}
              <div className="panel" key={`${page}-${theme}`}>
                {!events || !spec || !status ? <p className="muted">Loading the ledger…</p> : (
                  <>
                    {page === "overview" && <OverviewView run={run} events={events} status={status} onOpenAgent={openAgent} />}
                    {page === "agents" && <AgentsView spec={spec} events={events} status={status} />}
                    {page === "data" && <DataView runId={run.id} events={events} />}
                    {page === "loop" && <LoopView events={events} />}
                    {page === "test" && <TestView runId={run.id} events={events} />}
                    {page === "drivers" && <DriversView runId={run.id} events={events} />}
                    {page === "ledger" && <LedgerView events={events} spec={spec} agent={agent} onAgent={setAgent} />}
                    {page === "report" && <ReportView runId={run.id} events={events} />}
                  </>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
