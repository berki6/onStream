import { useQuery } from "@tanstack/react-query";

import { getPlaylist, listPlaylistVideos, listPlaylists } from "@/api/playlists";
import { playlistKeys } from "./keys";

export function usePlaylistsQuery(opts?: {
  enabled?: boolean;
  containsVideo?: string;
}) {
  const containsVideo = opts?.containsVideo;
  return useQuery({
    queryKey: containsVideo
      ? playlistKeys.listForVideo(containsVideo)
      : playlistKeys.list(),
    enabled: opts?.enabled ?? true,
    queryFn: async () =>
      (await listPlaylists(0, 50, containsVideo)).data || [],
  });
}

export function usePlaylistQuery(id: number | undefined) {
  return useQuery({
    queryKey: playlistKeys.detail(id || 0),
    enabled: Boolean(id),
    queryFn: async () => (await getPlaylist(id!)).data,
  });
}

export function usePlaylistVideosQuery(id: number | undefined) {
  return useQuery({
    queryKey: playlistKeys.videos(id || 0),
    enabled: Boolean(id),
    queryFn: async () => (await listPlaylistVideos(id!)).data || [],
  });
}
