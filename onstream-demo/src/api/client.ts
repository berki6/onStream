import { reportApiResult } from "../lib/connectivity";
import { storage } from "../lib/storage";

export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string | null;
  request_id?: string;
  pagination?: {
    total_count: number;
    page: number;
    per_page: number;
    has_more: boolean;
  };
};

export type ApiErrorBody = {
  success?: boolean;
  error?: {
    code?: string;
    message?: string;
    details?: Array<{ field?: string; message?: string; code?: string }> | null;
  };
  request_id?: string;
};

export class ApiError extends Error {
  status: number;
  code: string | null;
  body: unknown;

  constructor(
    message: string,
    status: number,
    body?: unknown,
    code: string | null = null
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
  }
}

export class NetworkError extends ApiError {
  constructor(message = "Can't reach OnStream. Check your connection.") {
    super(message, 0, null, "NETWORK");
    this.name = "NetworkError";
  }
}

export function isNetworkError(e: unknown): boolean {
  if (e instanceof NetworkError) return true;
  if (e instanceof ApiError && (e.status === 0 || e.code === "NETWORK")) {
    return true;
  }
  if (typeof e === "object" && e && (e as { name?: string }).name === "AbortError") {
    return true;
  }
  if (e instanceof Error) {
    const m = e.message.toLowerCase();
    return (
      m.includes("network request failed") ||
      m.includes("failed to fetch") ||
      m.includes("network error") ||
      m.includes("internet connection")
    );
  }
  return false;
}

/** Inline copy for buttons/forms. List screens hide network errors (banner covers them). */
export function userFacingError(e: unknown, fallback: string): string {
  if (isNetworkError(e)) {
    return e instanceof Error && e.message
      ? e.message
      : "Can't reach OnStream. Check your connection.";
  }
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}

export function queryErrorText(
  isError: boolean,
  error: unknown,
  hasData = false
): string | null {
  if (!isError || hasData || isNetworkError(error)) return null;
  return userFacingError(error, "Something went wrong");
}

const FETCH_TIMEOUT_MS = 12_000;

function toNetworkError(e: unknown): NetworkError {
  if (e instanceof NetworkError) return e;
  if (typeof e === "object" && e && (e as { name?: string }).name === "AbortError") {
    return new NetworkError("Request timed out. Try again.");
  }
  return new NetworkError("Can't reach OnStream. Check your connection.");
}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = FETCH_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (e) {
    throw toNetworkError(e);
  } finally {
    clearTimeout(timer);
  }
}

const DEFAULT_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

let apiBaseOverride: string | null = null;

export async function initApiBase() {
  const stored = await storage.getApiBase();
  if (stored) apiBaseOverride = stored.replace(/\/$/, "");
}

export function getApiBase() {
  return (apiBaseOverride || DEFAULT_BASE).replace(/\/$/, "");
}

export async function setApiBase(url: string) {
  const clean = url.trim().replace(/\/$/, "");
  apiBaseOverride = clean;
  await storage.setApiBase(clean);
}

type RequestOptions = {
  method?: string;
  body?: BodyInit | null;
  headers?: Record<string, string>;
  auth?: boolean;
  form?: boolean;
};

/** Public hydrate helper for AuthProvider boot (expired access + refresh). */
export async function tryRefreshAccessToken(): Promise<string | null> {
  return refreshAccessToken();
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = await storage.getRefreshToken();
  if (!refresh) return null;
  const res = await fetchWithTimeout(`${getApiBase()}/v1/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) return null;
  const json = (await res.json()) as ApiEnvelope<{
    access_token: string;
    token_type: string;
    expires_in?: number;
  }>;
  if (!json?.data?.access_token) return null;
  await storage.setAccessToken(json.data.access_token);
  return json.data.access_token;
}

function parseApiError(json: unknown, status: number): ApiError {
  if (typeof json === "object" && json) {
    const body = json as ApiErrorBody;
    const code = body.error?.code ?? null;
    const message =
      body.error?.message ||
      (typeof (json as { message?: unknown }).message === "string"
        ? (json as { message: string }).message
        : null) ||
      `Request failed (${status})`;
    return new ApiError(message, status, json, code);
  }
  return new ApiError(`Request failed (${status})`, status, json, null);
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    method = "GET",
    body = null,
    headers = {},
    auth = true,
    form = false,
  } = options;

  const url = path.startsWith("http") ? path : `${getApiBase()}${path}`;
  const reqHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (!form && body && !reqHeaders["Content-Type"]) {
    reqHeaders["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = await storage.getAccessToken();
    if (token) reqHeaders.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetchWithTimeout(url, { method, headers: reqHeaders, body });
  } catch (e) {
    reportApiResult(false);
    throw toNetworkError(e);
  }

  if (res.status === 401 && auth) {
    try {
      const next = await refreshAccessToken();
      if (next) {
        reqHeaders.Authorization = `Bearer ${next}`;
        res = await fetchWithTimeout(url, { method, headers: reqHeaders, body });
      }
    } catch (e) {
      if (isNetworkError(e)) {
        reportApiResult(false);
        throw toNetworkError(e);
      }
    }
  }

  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = text;
  }

  if (!res.ok) {
    throw parseApiError(json, res.status);
  }

  reportApiResult(true);
  return json as T;
}

export async function checkHealth(): Promise<{ status?: string } | null> {
  const url = `${getApiBase()}/health`;
  try {
    const res = await fetchWithTimeout(url, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    reportApiResult(true);
    return (await res.json()) as { status?: string };
  } catch {
    reportApiResult(false);
    return null;
  }
}

/** Same as checkHealth, but returns a UI string including the URL tried. */
export async function pingHealthLabel(): Promise<string> {
  const base = getApiBase();
  const url = `${base}/health`;
  try {
    const res = await fetchWithTimeout(url, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return `Unreachable · HTTP ${res.status} · ${url}`;
    const body = (await res.json()) as { data?: { status?: string }; status?: string };
    const status = body?.data?.status ?? body?.status ?? "ok";
    reportApiResult(true);
    return `API reachable · ${status} · ${url}`;
  } catch (e) {
    reportApiResult(false);
    const msg = isNetworkError(e)
      ? "no connection"
      : e instanceof Error
        ? e.message
        : "network error";
    return `Unreachable · ${msg} · ${url}`;
  }
}
