import { apiRequest, type ApiEnvelope } from "./client";

export type ShareLink = {
  public_id: string;
  video_id: string;
  label?: string | null;
  expires_at: string;
  revoked_at?: string | null;
  max_views?: number | null;
  view_count: number;
  created_at?: string | null;
  active: boolean;
  token?: string;
  watch_url?: string;
  share_url?: string;
  app_url?: string;
};

export type ShareExchange = {
  token: string;
  expires_in: number;
  playback_url: string;
  upload_id: string;
  title: string;
  expires_at: string;
};

export async function createShareLink(input: {
  videoId: string;
  expiresInSeconds: number;
  label?: string;
  maxViews?: number;
}) {
  return apiRequest<ApiEnvelope<ShareLink>>("/v1/share-links", {
    method: "POST",
    body: JSON.stringify({
      video_id: input.videoId,
      expires_in_seconds: input.expiresInSeconds,
      label: input.label,
      max_views: input.maxViews,
    }),
  });
}

export async function listShareLinks(videoId?: string) {
  const q = videoId ? `?video_id=${encodeURIComponent(videoId)}` : "";
  return apiRequest<ApiEnvelope<ShareLink[]>>(`/v1/share-links${q}`);
}

export async function revokeShareLink(publicId: string) {
  return apiRequest<ApiEnvelope<ShareLink>>(`/v1/share-links/${publicId}`, {
    method: "DELETE",
  });
}

export async function exchangeShareLink(publicId: string, token: string) {
  return apiRequest<ApiEnvelope<ShareExchange>>(
    `/v1/share-links/${publicId}/exchange`,
    {
      method: "POST",
      body: JSON.stringify({ token }),
      auth: false,
    }
  );
}
