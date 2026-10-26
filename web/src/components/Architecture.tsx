import type { NodeStatus } from "../ledger";

/* System architecture, drawn in code on an 8-column grid inside a 1240 × 600 viewBox. Agent boxes
   are coloured by their live status from the ledger; clicking one opens its ledger entries. */

const W = 112;
const H = 58;
const ROW1 = 150;
const ROW2 = 330;
const X = [230, 351, 472, 593, 714, 835, 956, 1077];

const POS: Record<string, [number, number]> = {
  schema_adapter: [X[0], ROW1], ingestion: [X[1], ROW1], profiler: [X[2], ROW1], eda: [X[3], ROW1],
  cleaner: [X[4], ROW1], features: [X[5], ROW1], leakage_guard: [X[6], ROW1], splitter: [X[7], ROW1],
  trainer: [X[1], ROW2], evaluator: [X[2], ROW2], critic: [X[3], ROW2],
  tester: [X[5], ROW2], explainer: [X[6], ROW2], reporter: [X[7], ROW2],
};
const KIND: Record<string, string> = {
  schema_adapter: "rule + LLM ✦", ingestion: "rule", profiler: "rule", eda: "rule + LLM ✦", cleaner: "rule",
  features: "rule", leakage_guard: "rule · guard", splitter: "locks the test", trainer: "LightGBM & co.",
  evaluator: "validation only", critic: "whitelist ✦", tester: "runs once", explainer: "SHAP + LLM ✦",
  reporter: "rule",
};
const LABEL: Record<string, string> = { leakage_guard: "leakage guard", schema_adapter: "schema adapter" };

const cx = (n: string) => POS[n][0] + W / 2;
const cy = (n: string) => POS[n][1] + H / 2;
const right = (n: string) => POS[n][0] + W;
const bottom = (n: string) => POS[n][1] + H;

function Edge(props: { d: string; dashed?: boolean; tone?: "loop" | "lock" | "halt" }) {
  return (
    <path d={props.d} className={`edge ${props.tone ?? ""}`} strokeDasharray={props.dashed ? "4 4" : undefined}
      markerEnd={`url(#arrow${props.tone ? "-" + props.tone : ""})`} />
  );
}

function Agent(props: { name: string; status?: NodeStatus; onClick: () => void }) {
  const [x, y] = POS[props.name];
  const s = props.status;
  const state = s?.state ?? "pending";
  const time = state === "running" ? "working…" : s?.seconds != null ? `${s.seconds}s${s.runs > 1 ? ` · ×${s.runs}` : ""}` : "";
  return (
    <g className={`arch-agent ${state}`} transform={`translate(${x} ${y})`} onClick={props.onClick}
      role="button" tabIndex={0} aria-label={`${props.name}: ${state}`}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && props.onClick()}>
      <rect width={W} height={H} rx={8} />
      {state === "running" && <rect className="scan" width={W} height={3} y={H - 3} rx={1.5} />}
      <text x={10} y={21} className="t-name">{LABEL[props.name] ?? props.name}</text>
      <text x={10} y={37} className="t-kind">{KIND[props.name]}</text>
      <text x={10} y={51} className="t-time">{time}</text>
    </g>
  );
}

function Pill(props: { x: number; y: number; w: number; title: string; sub: string }) {
  return (
    <g className="arch-source" transform={`translate(${props.x} ${props.y})`}>
      <rect width={props.w} height={48} rx={24} />
      <text x={props.w / 2} y={21} textAnchor="middle" className="t-name">{props.title}</text>
      <text x={props.w / 2} y={36} textAnchor="middle" className="t-kind">{props.sub}</text>
    </g>
  );
}

export function Architecture(props: {
  status: Record<string, NodeStatus> | null;
  source: { title: string; sub: string };
  onSelect: (node: string) => void;
}) {
  const chain = (names: string[]) =>
    names.slice(0, -1).map((a, i) => <Edge key={a} d={`M${right(a)} ${cy(a)} H${POS[names[i + 1]][0]}`} />);
  const halted = props.status?.leakage_guard?.state === "halted";

  return (
    <div className="arch-scroll">
      <svg className="arch" viewBox="0 0 1240 600" role="img"
        aria-label="Pipeline architecture: dataset, schema adapter, data agents, locked split, training loop, ledger and console">
        <defs>
          {[["", "var(--faint)"], ["-loop", "var(--accent)"], ["-lock", "var(--ink)"], ["-halt", "var(--bad)"]].map(([id, c]) => (
            <marker key={id} id={`arrow${id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" fill={c} />
            </marker>
          ))}
        </defs>

        <text x={X[0]} y={136} className="t-lane">Data agents</text>
        <text x={X[1]} y={318} className="t-lane">Modelling agents</text>
        <text x={40} y={136} className="t-lane">Dataset</text>

        {/* sources */}
        <Pill x={40} y={155} w={150} title={props.source.title} sub={props.source.sub} />
        <Pill x={740} y={30} w={110} title="ERA5" sub="boundary layer" />
        <Pill x={905} y={30} w={110} title="CAMS" sub="day-ahead forecast" />
        <Edge d={`M190 ${cy("schema_adapter")} H${POS.schema_adapter[0]}`} />
        <Edge d={`M795 78 V110 H870 V${ROW1}`} />
        <Edge d={`M960 78 V110 H912 V${ROW1}`} />

        {/* data lane */}
        {chain(["schema_adapter", "ingestion", "profiler", "eda", "cleaner", "features", "leakage_guard", "splitter"])}
        <Edge d={`M${cx("leakage_guard")} ${bottom("leakage_guard")} V244`} dashed tone="halt" />
        <g className={`arch-halt${halted ? " on" : ""}`} transform={`translate(${cx("leakage_guard") - 40} 244)`}>
          <rect width={80} height={26} rx={13} />
          <text x={40} y={17} textAnchor="middle">halt on leak</text>
        </g>

        {/* split: train/val to the loop, test to the vault */}
        <Edge d={`M${cx("splitter")} ${bottom("splitter")} V296 H${cx("trainer")} V${ROW2}`} />
        <text x={cx("cleaner")} y={290} className="t-edge" textAnchor="middle">train · validation years</text>
        <Edge d={`M${right("splitter")} ${cy("splitter") + 12} H1222 V470 H${right("tester")}`} tone="lock" />
        <text x={1214} y={462} className="t-edge" textAnchor="end">test year, hashed</text>
        <g className="arch-vault" transform={`translate(${POS.tester[0]} 446)`}>
          <rect width={W} height={48} rx={8} />
          <text x={W / 2} y={21} textAnchor="middle" className="t-name">locked test</text>
          <text x={W / 2} y={36} textAnchor="middle" className="t-kind">read once by tester</text>
        </g>
        <Edge d={`M${cx("tester")} 446 V${bottom("tester")}`} tone="lock" />

        {/* modelling lane + critic loop */}
        {chain(["trainer", "evaluator", "critic"])}
        <Edge d={`M${right("critic")} ${cy("critic")} H${POS.tester[0]}`} />
        <text x={(right("critic") + POS.tester[0]) / 2} y={cy("critic") - 8} className="t-edge" textAnchor="middle">STOP</text>
        {chain(["tester", "explainer", "reporter"])}
        <Edge d={`M${cx("critic")} ${bottom("critic")} V424 H${cx("trainer")} V${bottom("trainer")}`} tone="loop" />
        <text x={(cx("critic") + cx("trainer")) / 2} y={442} className="t-edge loop" textAnchor="middle">
          one whitelisted action per iteration
        </text>

        {Object.keys(POS).map((name) => (
          <Agent key={name} name={name} status={props.status?.[name]} onClick={() => props.onSelect(name)} />
        ))}

        <g className="arch-llm" transform="translate(40 330)">
          <rect width={150} height={58} rx={8} />
          <text x={12} y={22} className="t-name">✦ Claude</text>
          <text x={12} y={38} className="t-kind">mapping · notes · critic</text>
          <text x={12} y={51} className="t-kind">cached for replay</text>
        </g>
        <g className="arch-bus" transform="translate(40 530)">
          <rect width={1160} height={40} rx={8} />
          <text x={16} y={25} className="t-name">Experiment ledger</text>
          <text x={150} y={25} className="t-kind">every agent appends its decisions to runs/&lt;id&gt;/ledger.jsonl</text>
          <text x={1144} y={25} textAnchor="end" className="t-kind">→ FastAPI → this console</text>
        </g>
      </svg>
    </div>
  );
}
