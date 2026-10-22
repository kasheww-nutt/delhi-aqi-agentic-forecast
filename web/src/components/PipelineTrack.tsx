import { humanName, type NodeStatus } from "../ledger";
import type { SpecNode } from "../types";

const DATA_LANE = ["ingestion", "profiler", "eda", "cleaner", "features", "leakage_guard", "splitter"];

function Agent(props: { node: SpecNode; status: NodeStatus; active: boolean; onClick: () => void }) {
  const { node, status } = props;
  const time =
    status.state === "running" ? "working…" : status.seconds !== null ? `${status.seconds}s` : "";
  return (
    <button className={`agent ${status.state}`} aria-pressed={props.active} onClick={props.onClick}
      title={`${humanName(node.name)} — ${status.state}`}>
      <div className="name">{humanName(node.name)}</div>
      <div className="kind">{node.kind}</div>
      <div className="time">
        {time}
        {status.runs > 1 && ` · ×${status.runs}`}
      </div>
    </button>
  );
}

export function PipelineTrack(props: {
  spec: SpecNode[];
  status: Record<string, NodeStatus>;
  focus: string | null;
  onFocus: (node: string) => void;
}) {
  const lane = (names: string[]) =>
    names.flatMap((name, i) => {
      const node = props.spec.find((n) => n.name === name);
      if (!node) return [];
      const items = [
        <Agent key={name} node={node} status={props.status[name]} active={props.focus === name}
          onClick={() => props.onFocus(name)} />,
      ];
      if (i < names.length - 1) items.push(<span key={`${name}-a`} className="arrow" aria-hidden="true">→</span>);
      return items;
    });
  const modelLane = props.spec.map((n) => n.name).filter((n) => !DATA_LANE.includes(n));
  const iterations = props.status["trainer"]?.runs ?? 0;

  return (
    <section className="track" aria-label="Pipeline agents">
      <p className="lane-title">Data agents</p>
      <div className="lane">{lane(DATA_LANE)}</div>
      <p className="lane-title" style={{ marginTop: 14 }}>Modelling agents</p>
      <div className="lane">{lane(modelLane)}</div>
      <p className="loop-note">
        critic ⟲ trainer: {iterations === 0 ? "loop not started" : `${iterations} training iteration${iterations > 1 ? "s" : ""}`}
      </p>
    </section>
  );
}
