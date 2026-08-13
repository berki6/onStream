import { apiRequest, type ApiEnvelope } from "./client";

export type Playlist = {
  id: number;
  name: string;
  user_id: number;
  is_public: boolean;
  created_at?: string | null;
  contains_video?: boolean | null;
};

export type PlaylistVideo = {
  upload_id: string;
  title: string;
  position: number;
  duration?: number | null;
  status?: string | null;
  thumbnail_path?: string | null;
};

export async function listPlaylists(
  skip = 0,
  limit = 50,
  containsVideo?: string
) {
  const q = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  });
  if (containsVideo) q.set("contains_video", containsVideo);
  return apiRequest<ApiEnvelope<Playlist[]>>(`/v1/playlists/?${q.toString()}`);
}

export async function getPlaylist(id: number) {
  return apiRequest<ApiEnvelope<Playlist>>(`/v1/playlists/${id}`);
}

export async function createPlaylist(name: string, isPublic = false) {
  return apiRequest<ApiEnvelope<Playlist>>("/v1/playlists/", {
    method: "POST",
    body: JSON.stringify({ name, is_public: isPublic }),
  });
}

export async function updatePlaylist(
  id: number,
  body: { name?: string; is_public?: boolean }
) {
  return apiRequest<ApiEnvelope<Playlist>>(`/v1/playlists/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deletePlaylist(id: number) {
  await apiRequest<null>(`/v1/playlists/${id}`, { method: "DELETE" });
}

export async function listPlaylistVideos(id: number) {
  return apiRequest<ApiEnvelope<PlaylistVideo[]>>(
    `/v1/playlists/${id}/videos`
  );
}

export async function addVideoToPlaylist(
  playlistId: number,
  videoId: string,
  position = 0
) {
  return apiRequest<ApiEnvelope<{ playlist_id: number; video_upload_id: string }>>(
    `/v1/playlists/${playlistId}/videos/${videoId}`,
    {
      method: "POST",
      body: JSON.stringify({ position }),
    }
  );
}

export async function removeVideoFromPlaylist(
  playlistId: number,
  videoId: string
) {
  await apiRequest<null>(
    `/v1/playlists/${playlistId}/videos/${videoId}`,
    { method: "DELETE" }
  );
}

export async function updatePlaylistVideoPosition(
  playlistId: number,
  videoId: string,
  position: number
) {
  return apiRequest<ApiEnvelope<{ position: number }>>(
    `/v1/playlists/${playlistId}/videos/${videoId}`,
    {
      method: "PUT",
      body: JSON.stringify({ position }),
    }
  );
}

export async function getPublicPlaylist(id: number) {
  return apiRequest<
    ApiEnvelope<{ id: number; name: string; videos: PlaylistVideo[] }>
  >(`/v1/playlists/public/${id}`, { auth: false });
}
