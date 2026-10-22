export type RunStatus = "running" | "done" | "halted" | "error";

export interface RunSummary {
  id: string;
  status: RunStatus;
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
  status: "start" | "info" | "done" | "halt" | "halted" | "error";
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
