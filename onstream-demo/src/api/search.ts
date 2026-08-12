import { apiRequest, type ApiEnvelope } from "./client";

export type SearchResult = {
  upload_id: string;
  title: string;
  description?: string | null;
  thumbnail_path?: string | null;
  score: number;
  status: string;
};

export type SearchResponse = {
  mode: string;
  q: string;
  results: SearchResult[];
};

export async function searchVideos(q: string, mode: "keyword" | "semantic" = "keyword") {
  const params = new URLSearchParams({ q, mode, limit: "40" });
  return apiRequest<ApiEnvelope<SearchResponse>>(`/v1/search/?${params}`);
}
