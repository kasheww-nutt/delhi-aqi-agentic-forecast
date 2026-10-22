import type { LedgerEvent, SpecNode } from "./types";

export type NodeState = "pending" | "running" | "done" | "halted" | "error";

export interface NodeStatus {
  state: NodeState;
  seconds: number | null;
  runs: number;
}

export function nodeStatus(spec: SpecNode[], events: LedgerEvent[]): Record<string, NodeStatus> {
  const out: Record<string, NodeStatus> = {};
  for (const n of spec) out[n.name] = { state: "pending", seconds: null, runs: 0 };
  for (const e of events) {
    const n = out[e.node];
    if (!n) continue;
    if (e.status === "start") {
      n.state = "running";
      n.runs += 1;
    } else if (e.status === "done" || e.status === "halted" || e.status === "error") {
      n.state = e.status;
      n.seconds = typeof e.seconds === "number" ? e.seconds : n.seconds;
    }
  }
  return out;
}

/** The agent's own report lines ("info" / "halt"), oldest first. */
export function reports(events: LedgerEvent[], node: string): LedgerEvent[] {
  return events.filter((e) => e.node === node && (e.status === "info" || e.status === "halt"));
}

/** True when the agent's report lists this artifact (avoids requesting files that were never written). */
export function hasArtifact(events: LedgerEvent[], node: string, name: string): boolean {
  return reports(events, node).some((e) => Array.isArray(e.artifacts) && (e.artifacts as string[]).includes(name));
}

export const clock =(ts: number) =>
  new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

export const humanName = (node: string) => node.replace("_", " ");
