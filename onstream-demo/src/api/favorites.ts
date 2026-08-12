import { apiRequest, type ApiEnvelope } from "./client";
import type { Video } from "./videos";

export async function listSavedVideos(limit = 50) {
  return apiRequest<ApiEnvelope<Video[]>>(`/v1/videos/saved?limit=${limit}`);
}

export async function favoriteVideo(videoId: string) {
  return apiRequest<ApiEnvelope<{ upload_id: string; favorited: boolean }>>(
    `/v1/videos/${videoId}/favorite`,
    { method: "PUT" }
  );
}

export async function unfavoriteVideo(videoId: string) {
  return apiRequest<ApiEnvelope<{ upload_id: string; favorited: boolean }>>(
    `/v1/videos/${videoId}/favorite`,
    { method: "DELETE" }
  );
}
