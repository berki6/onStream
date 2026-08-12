import { apiRequest, ApiEnvelope, ApiError, getApiBase } from "./client";
import { storage } from "../lib/storage";
import type { Video } from "./videos";

export type DirectUploadSession = {
  session_id: string;
  upload_id: string;
  upload_url: string;
  expires_at: string;
  storage_backend: string;
};

const DEFAULT_CHUNK = 512 * 1024; // 512 KiB — friendly for phone / LAN lab

export async function createDirectUploadSession(input: {
  title: string;
  description?: string;
  contentType?: string;
  isPublic?: boolean;
}) {
  return apiRequest<ApiEnvelope<DirectUploadSession>>("/v1/uploads", {
    method: "POST",
    body: JSON.stringify({
      title: input.title,
      description: input.description,
      content_type: input.contentType || "video/mp4",
      is_public: input.isPublic ?? false,
    }),
  });
}

export async function completeDirectUpload(sessionId: string) {
  return apiRequest<ApiEnvelope<Video>>(`/v1/uploads/${sessionId}/complete`, {
    method: "POST",
  });
}

async function authHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  const token = await storage.getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

/**
 * PUT one chunk (or whole body) to the upload session.
 * Supports Content-Range for resumable appends on the engine.
 */
export async function putUploadBytes(
  sessionId: string,
  body: ArrayBuffer | Blob,
  contentRange?: string
): Promise<void> {
  const url = `${getApiBase()}/v1/uploads/${sessionId}`;
  const headers = await authHeaders();
  if (contentRange) headers["Content-Range"] = contentRange;

  let res = await fetch(url, { method: "PUT", headers, body });
  if (res.status === 401) {
    // Let apiRequest refresh path stay single-source: one retry after soft refresh.
    const { tryRefreshAccessToken } = await import("./client");
    const next = await tryRefreshAccessToken();
    if (next) {
      headers.Authorization = `Bearer ${next}`;
      res = await fetch(url, { method: "PUT", headers, body });
    }
  }

  if (res.status === 204 || res.ok) return;

  let json: unknown = null;
  try {
    json = await res.json();
  } catch {
    json = null;
  }
  if (typeof json === "object" && json && "error" in (json as object)) {
    const err = json as {
      error?: { message?: string; code?: string };
    };
    throw new ApiError(
      err.error?.message || `Upload chunk failed (${res.status})`,
      res.status,
      json,
      err.error?.code ?? null
    );
  }
  throw new ApiError(`Upload chunk failed (${res.status})`, res.status, json);
}

export type DirectUploadProgress = {
  bytesSent: number;
  totalBytes: number;
  pct: number;
};

/**
 * Create session → chunked PUT → complete. Returns the Video row (PENDING/queued).
 */
export async function uploadVideoDirect(input: {
  uri: string;
  name: string;
  mimeType: string;
  title: string;
  description?: string;
  chunkSize?: number;
  onProgress?: (p: DirectUploadProgress) => void;
}): Promise<Video> {
  const sessionRes = await createDirectUploadSession({
    title: input.title,
    description: input.description,
    contentType: input.mimeType || "video/mp4",
  });
  const session = sessionRes.data;

  const fileRes = await fetch(input.uri);
  if (!fileRes.ok) {
    throw new ApiError("Could not read picked file", fileRes.status);
  }
  const blob = await fileRes.blob();
  const total = blob.size;
  const chunkSize = input.chunkSize ?? DEFAULT_CHUNK;
  let offset = 0;

  while (offset < total) {
    const end = Math.min(offset + chunkSize, total);
    const chunk = blob.slice(offset, end);
    const range = `bytes ${offset}-${end - 1}/${total}`;
    await putUploadBytes(session.session_id, chunk, range);
    offset = end;
    input.onProgress?.({
      bytesSent: offset,
      totalBytes: total,
      pct: total ? Math.round((offset / total) * 100) : 100,
    });
    // Yield so React Native can paint progress between chunks.
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }

  const done = await completeDirectUpload(session.session_id);
  return done.data;
}
