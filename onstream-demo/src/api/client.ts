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
    this.status = status;
    this.body = body;
    this.code = code;
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

async function refreshAccessToken(): Promise<string | null> {
  const refresh = await storage.getRefreshToken();
  if (!refresh) return null;
  const res = await fetch(`${getApiBase()}/v1/auth/token/refresh`, {
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

  let res = await fetch(url, { method, headers: reqHeaders, body });

  if (res.status === 401 && auth) {
    const next = await refreshAccessToken();
    if (next) {
      reqHeaders.Authorization = `Bearer ${next}`;
      res = await fetch(url, { method, headers: reqHeaders, body });
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

  return json as T;
}

export async function checkHealth(): Promise<{ status?: string } | null> {
  try {
    const res = await fetch(`${getApiBase()}/health`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as { status?: string };
  } catch {
    return null;
  }
}
