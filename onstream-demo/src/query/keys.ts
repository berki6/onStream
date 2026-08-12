export const videoKeys = {
  all: ["videos"] as const,
  list: () => [...videoKeys.all, "list"] as const,
  detail: (id: string) => [...videoKeys.all, "detail", id] as const,
  continue: () => [...videoKeys.all, "continue"] as const,
  saved: () => [...videoKeys.all, "saved"] as const,
  progress: (id: string) => [...videoKeys.all, "progress", id] as const,
  shares: (id: string) => [...videoKeys.all, "shares", id] as const,
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
