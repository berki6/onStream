import { apiRequest, type ApiEnvelope } from "./client";

export type SearchResult = {
  upload_id: string;
  title: string;
  description?: string | null;
  thumbnail_path?: string | null;
  score: number;
  status: string;
};

export type SearchCapabilities = {
  semantic_available: boolean;
  provider: string;
  indexed_videos: number;
  reason?: string | null;
};

export type SearchResponse = SearchCapabilities & {
  mode: string;
  q: string;
  results: SearchResult[];
  skipped_incompatible?: number;
};

export async function searchCapabilities() {
  return apiRequest<ApiEnvelope<SearchCapabilities>>("/v1/search/capabilities");
}

export async function searchVideos(
  q: string,
  mode: "keyword" | "semantic" = "keyword"
) {
  const params = new URLSearchParams({ q, mode, limit: "40" });
  return apiRequest<ApiEnvelope<SearchResponse>>(`/v1/search/?${params}`);
}
