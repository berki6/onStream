/**
 * Shared scroll physics so tabs/screens feel consistent.
 *
 * - iOS: `bounces` + `alwaysBounceVertical` → real rubber-band
 * - Android: `overScrollMode: "always"` → edge glow (OS has no iOS-style band)
 *
 * Library/Live use custom top-pull refresh (ElasticRefreshFlatList), so native
 * RefreshControl is not mounted on those lists.
 */
export const scrollPhysics = {
  bounces: true as const,
  alwaysBounceVertical: true as const,
  overScrollMode: "always" as const,
};

/** @deprecated Prefer `scrollPhysics` — kept for call-site clarity if needed */
export const listScrollPhysics = scrollPhysics;
