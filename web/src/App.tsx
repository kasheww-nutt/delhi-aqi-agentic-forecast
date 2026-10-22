import { useEffect, useState } from "react";
import { api, usePolling, useResource } from "./api";
import { LedgerFeed } from "./components/LedgerFeed";
import { PipelineTrack } from "./components/PipelineTrack";
import { RunRail } from "./components/RunRail";
import { nodeStatus } from "./ledger";
import type { RunSummary } from "./types";
import { DataView } from "./views/DataView";
import { DriversView } from "./views/DriversView";
import { LoopView } from "./views/LoopView";
import { ReportView } from "./views/ReportView";
import { TestView } from "./views/TestView";

const TABS = [
  { id: "data", label: "Data & cleaning" },
  { id: "loop", label: "Training loop" },
  { id: "test", label: "2025 test" },
  { id: "drivers", label: "Drivers" },
  { id: "report", label: "Results summary" },
] as const;
type Tab = (typeof TABS)[number]["id"];

const BANNER: Record<RunSummary["status"], (r: RunSummary) => string> = {
  running: () => "Pipeline running. This page updates as each agent reports.",
  done: () => "Pipeline finished. The 2025 test year was scored once.",
  halted: (r) => `Stopped: ${r.reason}`,
  error: (r) => `An agent failed: ${r.reason}`,
};

export default function App() {
  const spec = useResource(api.spec, []);
  const [selected, setSelected] = useState<string | null>(() => decodeURIComponent(location.hash.slice(1)) || null);
  const runs = usePolling(api.runs, [], true, 3000);
  const run = runs?.find((r) => r.id === selected) ?? runs?.[0];
  const runId = run?.id ?? null;
  const events = usePolling(() => (runId ? api.events(runId) : Promise.resolve([])), [runId],
    run?.status === "running");
  const [tab, setTab] = useState<Tab>("data");
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    if (runId) history.replaceState(null, "", `#${encodeURIComponent(runId)}`);
    setFocus(null);
  }, [runId]);

  const status = spec && events ? nodeStatus(spec, events) : null;

  return (
    <div className="shell">
      <RunRail runs={runs} selected={runId} onSelect={setSelected} />
      <main className="main">
        {!run ? (
          <div className="empty" style={{ marginTop: 40 }}>
            {runs === undefined ? "Connecting to the pipeline API…" : "No runs yet. Start one from the panel on the left."}
          </div>
        ) : (
          <>
            <header className="head">
              <div>
                <h1>Tomorrow's air, forecast today</h1>
                <div className="sub">
                  Run <span className="mono">{run.id}</span> · next-day CPCB AQI category for Delhi stations
                </div>
              </div>
              {run.test && (
                <div className="headline">
                  <div>
                    <div className="num">{run.test.macro_f1.toFixed(3)}</div>
                    <div className="lbl">2025 macro-F1 · {run.test.model}</div>
                  </div>
                  <div>
                    <div className="num muted">{run.test.persistence_f1.toFixed(3)}</div>
                    <div className="lbl">tomorrow = today</div>
                  </div>
                </div>
              )}
            </header>
            <div className={`banner ${run.status}`} role="status">{BANNER[run.status](run)}</div>

            {spec && status && <PipelineTrack spec={spec} status={status} focus={focus}
              onFocus={(n) => setFocus(focus === n ? null : n)} />}

            <div className="workspace">
              <div>
                <div className="tabs" role="tablist">
                  {TABS.map((t) => (
                    <button key={t.id} role="tab" className="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                      {t.label}
                    </button>
                  ))}
                </div>
                <div className="panel" role="tabpanel">
                  {!events ? <p className="muted">Loading the ledger…</p> : (
                    <>
                      {tab === "data" && <DataView runId={run.id} events={events} />}
                      {tab === "loop" && <LoopView events={events} />}
                      {tab === "test" && <TestView runId={run.id} events={events} />}
                      {tab === "drivers" && <DriversView runId={run.id} events={events} />}
                      {tab === "report" && <ReportView runId={run.id} events={events} />}
                    </>
                  )}
                </div>
              </div>
              <LedgerFeed events={events ?? []} focus={focus} onClear={() => setFocus(null)} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
