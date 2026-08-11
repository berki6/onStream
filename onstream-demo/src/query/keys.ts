export const videoKeys = {
  all: ["videos"] as const,
  list: () => [...videoKeys.all, "list"] as const,
  detail: (id: string) => [...videoKeys.all, "detail", id] as const,
};

export const liveKeys = {
  all: ["live"] as const,
  list: () => [...liveKeys.all, "list"] as const,
  detail: (id: string) => [...liveKeys.all, "detail", id] as const,
  health: (id: string) => [...liveKeys.all, "health", id] as const,
};
