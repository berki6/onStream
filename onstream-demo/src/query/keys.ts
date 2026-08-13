export const videoKeys = {
  all: ["videos"] as const,
  list: () => [...videoKeys.all, "list"] as const,
  detail: (id: string) => [...videoKeys.all, "detail", id] as const,
  continue: () => [...videoKeys.all, "continue"] as const,
  saved: () => [...videoKeys.all, "saved"] as const,
  history: () => [...videoKeys.all, "history"] as const,
  progress: (id: string) => [...videoKeys.all, "progress", id] as const,
  shares: (id: string) => [...videoKeys.all, "shares", id] as const,
  chapters: (id: string) => [...videoKeys.all, "chapters", id] as const,
};

export const playlistKeys = {
  all: ["playlists"] as const,
  list: () => [...playlistKeys.all, "list"] as const,
  listForVideo: (uploadId: string) =>
    [...playlistKeys.all, "list", "contains", uploadId] as const,
  detail: (id: number) => [...playlistKeys.all, "detail", id] as const,
  videos: (id: number) => [...playlistKeys.all, "videos", id] as const,
};

export const searchKeys = {
  all: ["search"] as const,
  query: (q: string) => [...searchKeys.all, q] as const,
};

export const liveKeys = {
  all: ["live"] as const,
  list: () => [...liveKeys.all, "list"] as const,
  detail: (id: string) => [...liveKeys.all, "detail", id] as const,
  health: (id: string) => [...liveKeys.all, "health", id] as const,
};
