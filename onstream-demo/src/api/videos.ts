import { apiRequest, ApiEnvelope, getApiBase } from "./client";

export type Video = {
  upload_id: string;
  title: string;
  description?: string | null;
  status: string;
  is_public: boolean;
  hls_path?: string | null;
  thumbnail_path?: string | null;
  caption_vtt_path?: string | null;
  transcript_path?: string | null;
  detected_language?: string | null;
  quality_score?: number | null;
  created_at?: string | null;
};

export type VideoChapter = {
  start: number;
  end?: number;
  title: string;
};

export type PlaybackToken = {
  token: string;
  expires_in: number;
  playback_url: string;
};

export async function listVideos(skip = 0, limit = 50) {
  return apiRequest<ApiEnvelope<Video[]>>(
    `/v1/videos/?skip=${skip}&limit=${limit}`
  );
}

export async function getVideo(videoId: string) {
  return apiRequest<ApiEnvelope<Video>>(`/v1/videos/${videoId}`);
}

export async function updateVideo(
  videoId: string,
  body: { title?: string; description?: string | null; is_public?: boolean }
) {
  return apiRequest<ApiEnvelope<Video>>(`/v1/videos/${videoId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteVideo(videoId: string) {
  await apiRequest<null>(`/v1/videos/${videoId}`, {
    method: "DELETE",
  });
}

export async function getVideoChapters(videoId: string) {
  return apiRequest<ApiEnvelope<{ chapters: VideoChapter[] }>>(
    `/v1/videos/${videoId}/chapters`
  );
}

export async function createPlaybackToken(videoId: string, expiresIn = 3600) {
  return apiRequest<ApiEnvelope<PlaybackToken>>(
    `/v1/videos/${videoId}/tokens`,
    {
      method: "POST",
      body: JSON.stringify({ expires_in: expiresIn, type: "playback" }),
    }
  );
}

export async function uploadVideoMultipart(input: {
  uri: string;
  name: string;
  mimeType: string;
  title: string;
  description?: string;
}) {
  const form = new FormData();
  form.append("title", input.title);
  if (input.description) form.append("description", input.description);
  form.append("file", {
    uri: input.uri,
    name: input.name,
    type: input.mimeType,
  } as unknown as Blob);

  return apiRequest<ApiEnvelope<Video>>("/v1/videos/", {
    method: "POST",
    form: true,
    body: form,
  });
}

export function absoluteMediaUrl(path?: string | null) {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${getApiBase()}${path.startsWith("/") ? "" : "/"}${path}`;
}
