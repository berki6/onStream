import { apiRequest, ApiEnvelope } from "./client";

export type LiveStream = {
  stream_id: string;
  title: string;
  status: string;
  is_public: boolean;
  stream_key_prefix: string;
  stream_key?: string;
  rtmp_url?: string | null;
  playback_url?: string | null;
  whip_url?: string | null;
  whep_url?: string | null;
  webrtc_base?: string | null;
  hls_path?: string | null;
  abr_hls_path?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  created_at?: string | null;
};

export type LiveHealth = {
  stream_id: string;
  status: string;
  playlist_present: boolean;
  playlist_age_seconds?: number | null;
  is_stale?: boolean;
  abr_running?: boolean;
  hls_path?: string | null;
};

export type LiveToken = {
  token: string;
  expires_in: number;
  playback_url: string;
};

export async function listLiveStreams(skip = 0, limit = 50) {
  return apiRequest<ApiEnvelope<LiveStream[]>>(
    `/v1/live/?skip=${skip}&limit=${limit}`
  );
}

export async function getLiveStream(streamId: string) {
  return apiRequest<ApiEnvelope<LiveStream>>(`/v1/live/${streamId}`);
}

export async function createLiveStream(title: string, isPublic = false) {
  return apiRequest<ApiEnvelope<LiveStream>>("/v1/live/", {
    method: "POST",
    body: JSON.stringify({ title, is_public: isPublic }),
  });
}

export async function deleteLiveStream(streamId: string) {
  return apiRequest<ApiEnvelope<{ deleted: boolean }>>(
    `/v1/live/${streamId}`,
    { method: "DELETE" }
  );
}

export async function getLiveHealth(streamId: string) {
  return apiRequest<ApiEnvelope<LiveHealth>>(`/v1/live/${streamId}/health`);
}

export async function createLiveToken(streamId: string, expiresIn = 3600) {
  return apiRequest<ApiEnvelope<LiveToken>>(`/v1/live/${streamId}/tokens`, {
    method: "POST",
    body: JSON.stringify({ expires_in: expiresIn, type: "playback" }),
  });
}
