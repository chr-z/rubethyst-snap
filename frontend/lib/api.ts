export function getPublicApiBase(): string {
  // When the UI is opened from localhost / loopback, always talk to the API on
  // the same host:8000. This avoids a stray NEXT_PUBLIC_API_BASE (e.g. prod)
  // breaking local dev and fixes IPv4 vs IPv6 hostname mismatches with CORS.
  if (typeof window !== "undefined") {
    const h = window.location.hostname;
    if (h === "localhost" || h === "127.0.0.1") {
      return `http://${h}:8000`;
    }
    if (h === "[::1]" || h === "::1") {
      return "http://[::1]:8000";
    }
  }
  const explicit = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (explicit && explicit.length > 0) {
    return explicit.replace(/\/$/, "");
  }
  return "http://localhost:8000";
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function humanizeNetworkError(err: unknown): string {
  if (!(err instanceof TypeError)) {
    return err instanceof Error ? err.message : "Pedido falhou.";
  }
  const m = err.message.toLowerCase();
  if (m.includes("fetch") || m.includes("network")) {
    return (
      "Sem ligação à API (CORS, URL errada ou servidor parado). " +
      "Em dev: API em http://localhost:8000, Redis a correr, e abre o site " +
      "em http://localhost:3000 (ou 127.0.0.1:3000 — ambos estão permitidos)."
    );
  }
  return err.message;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const base = getPublicApiBase();
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    throw new ApiError(0, humanizeNetworkError(err), err);
  }

  const text = await res.text();
  const data = text ? safeJson(text) : null;

  if (!res.ok) {
    const message = extractErrorMessage(data) ?? `HTTP ${res.status}`;
    throw new ApiError(res.status, message, data);
  }

  return (data ?? ({} as T)) as T;
}

function safeJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function extractErrorMessage(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as {
      message?: unknown;
      retry_after_seconds?: unknown;
      limit?: unknown;
      count?: unknown;
    };
    const msg = d.message;
    if (typeof msg === "string") {
      const retry =
        typeof d.retry_after_seconds === "number" && d.retry_after_seconds > 0
          ? ` Tenta de novo dentro de ~${Math.ceil(d.retry_after_seconds / 60)} min.`
          : "";
      const quota =
        typeof d.limit === "number" && typeof d.count === "number"
          ? ` (${d.count}/${d.limit} nesta hora).`
          : "";
      if (msg === "rate limit exceeded") {
        return (
          "Limite de pedidos por hora atingido para o plano usado neste pedido." +
          quota +
          retry
        );
      }
      return msg + retry;
    }
    return JSON.stringify(detail);
  }
  return null;
}
