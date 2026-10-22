import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, useResource } from "../api";
import { reports } from "../ledger";
import type { LedgerEvent } from "../types";

export function ReportView(props: { runId: string; events: LedgerEvent[] }) {
  const done = !!reports(props.events, "reporter")[0];
  const md = useResource(() => api.text(props.runId, "results_summary.md"), [props.runId, done]);
  if (!done || !md) return <p className="empty">The results summary is written at the end of a finished run.</p>;
  return (
    <section className="card md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{md.content}</ReactMarkdown>
    </section>
  );
}
