import {
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { getVideo, listVideos, type Video } from "@/api/videos";
import { videoKeys } from "./keys";

const IN_FLIGHT = new Set(["PENDING", "PROCESSING", "QUEUED", "UPLOADING"]);

/** Seed / merge list rows into per-id detail cache (warm navigations). */
export function seedVideoEntities(qc: QueryClient, items: Video[]) {
  for (const v of items) {
    qc.setQueryData(videoKeys.detail(v.upload_id), (prev: Video | undefined) =>
      prev ? { ...prev, ...v } : v
    );
  }
}

export function useVideosQuery(opts?: { enabled?: boolean }) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: videoKeys.list(),
    enabled: opts?.enabled ?? true,
    queryFn: async () => {
      const res = await listVideos();
      const items = res.data || [];
      seedVideoEntities(qc, items);
      return items;
    },
  });
}

export function useVideoQuery(
  id: string | undefined,
  opts?: { pollWhileBusy?: boolean; focused?: boolean }
) {
  const focused = opts?.focused ?? true;
  const pollWhileBusy = opts?.pollWhileBusy ?? true;

  return useQuery({
    queryKey: videoKeys.detail(id || ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const res = await getVideo(id!);
      return res.data;
    },
    refetchInterval: (query) => {
      if (!pollWhileBusy || !focused) return false;
      const v = query.state.data;
      if (!v) return false;
      const st = String(v.status || "").toUpperCase();
      if (IN_FLIGHT.has(st)) return 2500;
      // Soft poll captions for a while (dataUpdatedCount caps noise).
      if (st === "READY" && !v.caption_vtt_path) {
        return query.state.dataUpdateCount < 14 ? 2500 : false;
      }
      return false;
    },
  });
}

export function prefetchVideo(qc: QueryClient, id: string) {
  return qc.prefetchQuery({
    queryKey: videoKeys.detail(id),
    queryFn: async () => {
      const res = await getVideo(id);
      return res.data;
    },
  });
}
