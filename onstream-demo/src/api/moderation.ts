import { apiRequest, ApiEnvelope } from "./client";
import type { Video } from "./videos";

export type ModerationAction = "approve" | "reject";

export async function listModerationQueue(skip = 0, limit = 50) {
  return apiRequest<ApiEnvelope<Video[]>>(
    `/v1/moderation/queue?skip=${skip}&limit=${limit}`
  );
}

export async function reviewModeration(
  videoId: string,
  action: ModerationAction,
  makePublic?: boolean
) {
  return apiRequest<ApiEnvelope<Video>>(`/v1/moderation/${videoId}/review`, {
    method: "POST",
    body: JSON.stringify({
      action,
      make_public: makePublic ?? undefined,
    }),
  });
}
