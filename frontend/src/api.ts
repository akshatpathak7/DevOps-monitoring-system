import { useCallback, useEffect, useRef, useState } from "react";

export type Session = {
  authenticated: boolean;
  username?: string;
  csrf?: string;
};
export type MetricName =
  | "request_count"
  | "error_rate"
  | "latency"
  | "uptime"
  | "cpu"
  | "memory"
  | "up";
export type Service = {
  service_name: string;
  status: string;
  open_incidents: number;
  metrics: Record<MetricName | "requests_window", number | null>;
};
export type Summary = { services: Service[]; updated_at: string };
export type Log = {
  id?: number;
  timestamp: string;
  service_name: string;
  level: string;
  message: string;
};
export type Incident = {
  id: number;
  title: string;
  severity: string;
  incident_type: string;
  service_name: string;
  description: string;
  detected_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  status: string;
  metric_name: string;
  metric_value: number;
  threshold: number;
  window_seconds: number;
  metric_evidence: Record<string, number | null>;
  log_excerpt: Log[];
  likely_cause: string | null;
  ai_explanation: string | null;
  ai_recommendation: string[] | null;
  uncertainty_note: string | null;
  analysis_source: string | null;
  analysis_model: string | null;
  analyzed_at: string | null;
};
export type Page<T> = { items: T[]; total: number };
export type DemoStatus = {
  service_name: string;
  mode: string | null;
  expires_at: string | null;
};
export type Point = { timestamp: string; value: number | null };

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* non-JSON proxy error */
    }
    throw new Error(message);
  }
  return response.json();
}
export function post<T>(path: string, body: unknown, session: Session) {
  return api<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "X-CSRF-Token": session.csrf || "" },
  });
}
export function query(values: Record<string, string | number | undefined>) {
  const q = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") q.set(key, String(value));
  });
  return "?" + q.toString();
}
export function usePoll<T>(path: string | null, interval = 5000) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [updated, setUpdated] = useState<Date>();
  const refreshRef = useRef<() => void>(() => {});
  const refresh = useCallback(() => refreshRef.current(), []);
  useEffect(() => {
    let disposed = false,
      busy = false;
    const controller = new AbortController();
    setData(undefined);
    setError("");
    setLoading(true);
    async function load() {
      if (!path || busy || disposed) return;
      busy = true;
      try {
        const result = await api<T>(path, { signal: controller.signal });
        if (!disposed) {
          setData(result);
          setError("");
          setUpdated(new Date());
        }
      } catch (e) {
        if (!disposed) setError((e as Error).message);
      } finally {
        busy = false;
        if (!disposed) setLoading(false);
      }
    }
    refreshRef.current = () => {
      void load();
    };
    void load();
    const timer = setInterval(() => {
      void load();
    }, interval);
    return () => {
      disposed = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [path, interval]);
  return { data, error, loading, updated, refresh };
}
export const date = (value: string) => new Date(value).toLocaleString();
export const number = (value: number | null | undefined, digits = 1) =>
  value == null
    ? "—"
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });
export const label = (value: string) => value.replaceAll("_", " ");
