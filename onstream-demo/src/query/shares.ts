import { useQuery } from "@tanstack/react-query";

import { listShareLinks } from "@/api/shareLinks";
import { shareKeys } from "./keys";

export function useShareLinksQuery() {
  return useQuery({
    queryKey: shareKeys.list(),
    queryFn: async () => (await listShareLinks()).data || [],
  });
}
