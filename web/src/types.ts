export type RunStatus = "running" | "done" | "halted" | "error";

export interface DatasetConfig {
  name: string;
  project: string;
  format: "native" | "canonical" | "auto";
  years: [number, number];
  adapted: { stations: number; granularity: string; city: string | null; start: string; end: string } | null;
}

export interface SchemaReport {
  source: string;
  files_used: { file: string; layout: string; timestamp: string; station: string; tz: string; granularity: string }[];
  files_skipped: { file: string; reason: string }[];
  metadata_files: string[];
  granularity: string;
  city_filter: string | null;
  stations: number;
  rows: number;
  start: string;
  end: string;
  mappings: { source: string; canonical: string; unit_from: string; unit_to: string; conversion: string; by: string }[];
  ignored: { column: string; reason: string }[];
  missing_variables: string[];
  out_of_range_set_missing: Record<string, number>;
  coverage_pct: Record<string, number>;
  warnings: string[];
  suggested_settings?: { split: Record<"train" | "val" | "test", [string, string]> };
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  dataset: string;
  started: number | null;
  finished: number | null;
  reason: string;
  test?: { model: string; macro_f1: number; persistence_f1: number };
}

export interface SpecNode {
  name: string;
  kind: string;
}

export interface LedgerEvent {
  ts: number;
  node: string;
  status: "start" | "info" | "done" | "halt" | "halted" | "error" | "llm";
  summary?: string;
  seconds?: number;
  [key: string]: unknown;
}

export interface Scores {
  macro_f1: number;
  severe_recall: number;
  accuracy: number;
  within_one_category: number;
  train_macro_f1?: number;
  mean_category_error?: number;
  weighted_f1?: number;
  per_class_recall?: number[];
  confusion?: number[][];
  n?: number;
}

export interface CriticDecision {
  diagnosis: string;
  action: string;
  rationale: string;
  by?: string;
}

export interface StationForecast {
  dates: string[];
  actual: number[];
  predicted: number[];
  persistence: number[];
}

export const CATEGORIES = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"] as const;

export interface ScoutRun {
  id: string;
  status: "running" | "done" | "error";
  station: string;
  started: number | null;
  finished: number | null;
  brief: string | null;
  error: string | null;
  events: LedgerEvent[];
}
