import { useEffect, useState } from "react";
import type { LedgerEvent, RunSummary, SpecNode, StationForecast } from "./types";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

export const api = {
  spec: () => get<SpecNode[]>("/api/spec"),
  runs: () => get<RunSummary[]>("/api/runs"),
  events: (id: string) => get<LedgerEvent[]>(`/api/runs/${id}/events`),
  predictions: (id: string) => get<Record<string, StationForecast>>(`/api/runs/${id}/predictions`),
  shap: (id: string) => get<{ feature: string; importance: number }[]>(`/api/runs/${id}/shap`),
  text: (id: string, name: string) => get<{ content: string }>(`/api/runs/${id}/text/${name}`),
  artifactUrl: (id: string, name: string) => `/api/runs/${id}/artifacts/${name}`,
  startRun: async (body: { leaky_demo: boolean; no_llm: boolean }) => {
    const r = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`Could not start a run (${r.status})`);
    return (await r.json()) as { id: string };
  },
};

/** Fetch once per key; returns undefined while loading and null when the resource is missing. */
export function useResource<T>(load: () => Promise<T>, deps: unknown[]): T | null | undefined {
  const [value, setValue] = useState<T | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setValue(undefined);
    load()
      .then((v) => live && setValue(v))
      .catch(() => live && setValue(null));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return value;
}

/** Poll a loader while `active` is true. */
export function usePolling<T>(load: () => Promise<T>, deps: unknown[], active: boolean, ms = 2000) {
  const [value, setValue] = useState<T | undefined>(undefined);
  useEffect(() => {
    let live = true;
    const tick = () => load().then((v) => live && setValue(v)).catch(() => undefined);
    tick();
    const t = active ? setInterval(tick, ms) : undefined;
    return () => {
      live = false;
      if (t) clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, active]);
  return value;
}
