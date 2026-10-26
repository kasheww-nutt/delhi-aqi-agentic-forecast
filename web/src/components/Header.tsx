import { ChevronDown, ChevronRight, Moon, Plus, Sun } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { RunSummary } from "../types";
import { NewRunDialog } from "./NewRunDialog";

const STATUS: Record<RunSummary["status"], string> = { running: "running", done: "finished", halted: "stopped by guard", error: "failed" };

function RunSwitcher(props: { runs: RunSummary[] | undefined; selected: string | null; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const current = props.runs?.find((r) => r.id === props.selected);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div className="run-switch" ref={box}>
      <button onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open} aria-label="Switch run">
        {current && <span className={`dot ${current.status}`} />}
        <span className="txt">{current?.id ?? "Select a run"}</span>
        <ChevronDown aria-hidden="true" />
      </button>
      {open && (
        <div className="menu" role="listbox" aria-label="Runs">
          {props.runs?.map((r) => (
            <button key={r.id} role="option" aria-selected={r.id === props.selected}
              onClick={() => { props.onSelect(r.id); setOpen(false); }}>
              <span className={`dot ${r.status}`} />
              <span className="mid">{r.id}</span>
              <span className="mres">{r.test ? r.test.macro_f1.toFixed(3) : ""}</span>
              <span className="mdesc">
                {r.dataset} · {r.test ? `${r.test.model} vs persistence ${r.test.persistence_f1.toFixed(3)}` : STATUS[r.status]}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Header(props: {
  pageLabel: string;
  runs: RunSummary[] | undefined;
  selected: string | null;
  onSelect: (id: string) => void;
  theme: "dark" | "light";
  onTheme: () => void;
}) {
  const [dialog, setDialog] = useState(false);
  return (
    <header className="header">
      <div className="crumbs">
        <span>Runs</span>
        <ChevronRight aria-hidden="true" />
        <b>{props.pageLabel}</b>
      </div>
      <span className="spacer" />
      <RunSwitcher runs={props.runs} selected={props.selected} onSelect={props.onSelect} />
      <button className="icon-btn" onClick={props.onTheme}
        aria-label={props.theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        title={props.theme === "dark" ? "Light mode" : "Dark mode"}>
        {props.theme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
      </button>
      <button className="btn" onClick={() => setDialog(true)}><Plus aria-hidden="true" />New run</button>
      {dialog && <NewRunDialog onClose={() => setDialog(false)} onStarted={(id) => { props.onSelect(id); setDialog(false); }} />}
    </header>
  );
}
