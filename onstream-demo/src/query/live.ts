import {
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import {
  getLiveHealth,
  getLiveStream,
  listLiveStreams,
  type LiveHealth,
  type LiveStream,
} from "@/api/live";
import { liveKeys } from "./keys";

export function seedLiveEntities(qc: QueryClient, items: LiveStream[]) {
  for (const s of items) {
    qc.setQueryData(liveKeys.detail(s.stream_id), (prev: LiveStream | undefined) =>
      prev ? { ...prev, ...s } : s
    );
  }
}

export function useLiveListQuery(opts?: { enabled?: boolean }) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: liveKeys.list(),
    enabled: opts?.enabled ?? true,
    queryFn: async () => {
      const res = await listLiveStreams(0, 50, { includeEnded: true });
      const items = res.data || [];
      seedLiveEntities(qc, items);
      return items;
    },
  });
}

export function useLiveStreamQuery(
  id: string | undefined,
  opts?: { focused?: boolean }
) {
  const focused = opts?.focused ?? true;
  return useQuery({
    queryKey: liveKeys.detail(id || ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const res = await getLiveStream(id!);
      return res.data;
    },
    refetchInterval: focused ? 8_000 : false,
  });
}

export function useLiveHealthQuery(
  id: string | undefined,
  opts?: { focused?: boolean; enabled?: boolean }
) {
  const focused = opts?.focused ?? true;
  return useQuery({
    queryKey: liveKeys.health(id || ""),
    enabled: Boolean(id) && (opts?.enabled ?? true),
    queryFn: async () => {
      const res = await getLiveHealth(id!);
      return res.data as LiveHealth;
    },
    refetchInterval: focused ? 5_000 : false,
  });
}

export function prefetchLive(qc: QueryClient, id: string) {
  return Promise.all([
    qc.prefetchQuery({
      queryKey: liveKeys.detail(id),
      queryFn: async () => {
        const res = await getLiveStream(id);
        return res.data;
      },
    }),
    qc.prefetchQuery({
      queryKey: liveKeys.health(id),
      queryFn: async () => {
        const res = await getLiveHealth(id);
        return res.data;
      },
    }),
  ]);
}
