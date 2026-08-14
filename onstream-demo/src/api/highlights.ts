import { apiRequest, ApiEnvelope } from "./client";

export type Highlight = {
  public_id: string;
  video_id: string;
  title: string;
  start: number;
  end: number;
  created_at?: string | null;
  playback_url?: string | null;
  watch_url?: string | null;
};

export async function listHighlights(videoId: string) {
  return apiRequest<ApiEnvelope<Highlight[]>>(
    `/v1/videos/${videoId}/highlights`
  );
}

export async function createHighlight(
  videoId: string,
  body: { start: number; end: number; title?: string }
) {
  return apiRequest<ApiEnvelope<Highlight>>(
    `/v1/videos/${videoId}/highlights`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function importHighlightsFromChapters(videoId: string) {
  return apiRequest<ApiEnvelope<Highlight[]>>(
    `/v1/videos/${videoId}/highlights`,
    {
      method: "POST",
      body: JSON.stringify({ from_chapters: true }),
    }
  );
}

export async function deleteHighlight(videoId: string, highlightId: string) {
  return apiRequest<ApiEnvelope<{ deleted: boolean }>>(
    `/v1/videos/${videoId}/highlights/${highlightId}`,
    { method: "DELETE" }
  );
}

export async function createHighlightToken(videoId: string, highlightId: string) {
  return apiRequest<ApiEnvelope<{
    playback_url: string;
    clip_start?: number | null;
    clip_end?: number | null;
    title?: string;
  }>>(`/v1/videos/${videoId}/highlights/${highlightId}/tokens`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
