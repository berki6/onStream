import { apiRequest, type ApiEnvelope } from "./client";

export type ContinueItem = {
  upload_id: string;
  title: string;
  thumbnail_path?: string | null;
  status: string;
  position_seconds: number;
  duration_seconds?: number | null;
  completed: boolean;
  progress_ratio: number;
  last_watched_at?: string | null;
};

export type ProgressResponse = {
  upload_id: string;
  position_seconds: number;
  duration_seconds?: number | null;
  completed: boolean;
  last_watched_at?: string | null;
};

export async function listContinueWatching(limit = 20) {
  return apiRequest<ApiEnvelope<ContinueItem[]>>(
    `/v1/videos/continue?limit=${limit}`
  );
}

export async function listWatchHistory(limit = 50) {
  return apiRequest<ApiEnvelope<ContinueItem[]>>(
    `/v1/videos/history?limit=${limit}`
  );
}

export async function getWatchProgress(videoId: string) {
  return apiRequest<ApiEnvelope<ProgressResponse>>(
    `/v1/videos/${videoId}/progress`
  );
}

export async function upsertWatchProgress(
  videoId: string,
  positionSeconds: number,
  durationSeconds?: number | null
) {
  return apiRequest<ApiEnvelope<ProgressResponse>>(
    `/v1/videos/${videoId}/progress`,
    {
      method: "POST",
      body: JSON.stringify({
        position_seconds: positionSeconds,
        ...(durationSeconds != null
          ? { duration_seconds: durationSeconds }
          : {}),
      }),
    }
  );
}

export async function clearWatchProgress(videoId: string) {
  return apiRequest<ApiEnvelope<{ upload_id: string; cleared: boolean }>>(
    `/v1/videos/${videoId}/progress`,
    { method: "DELETE" }
  );
}

export async function dismissContinueItem(videoId: string) {
  return apiRequest<ApiEnvelope<{ upload_id: string; dismissed: boolean }>>(
    `/v1/videos/${videoId}/continue`,
    { method: "DELETE" }
  );
}

export async function clearContinueWatching() {
  return apiRequest<ApiEnvelope<{ cleared: boolean; deleted: number }>>(
    `/v1/videos/continue`,
    { method: "DELETE" }
  );
}

export async function clearWatchHistory() {
  return apiRequest<ApiEnvelope<{ cleared: boolean; deleted: number }>>(
    `/v1/videos/history`,
    { method: "DELETE" }
  );
}
