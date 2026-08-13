import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter, type Href } from "expo-router";
import { onlineManager, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { listSavedVideos } from "@/api/favorites";
import { listContinueWatching } from "@/api/watch";
import { queryErrorText } from "@/api/client";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { LibraryShelves } from "@/components/LibraryShelves";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { VideoUploadComposer } from "@/components/VideoUploadComposer";
import { videoPipelineHint } from "@/lib/videoStatus";
import { videoKeys } from "@/query/keys";
import { usePlaylistsQuery } from "@/query/playlists";
import { prefetchVideo, useVideosQuery } from "@/query/videos";
import { colors, radii, spacing } from "@/theme/tokens";

const IN_FLIGHT = new Set(["PENDING", "PROCESSING", "QUEUED", "UPLOADING"]);

const HINT_COLOR = {
  ok: colors.ready,
  warn: colors.warning,
  danger: colors.danger,
  muted: colors.textDim,
} as const;

export default function VideosScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const qc = useQueryClient();
  const [composerOpen, setComposerOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const focusedRef = useRef(true);

  const {
    data: items = [],
    isPending,
    isError,
    error,
    refetch,
  } = useVideosQuery();

  const continueQuery = useQuery({
    queryKey: videoKeys.continue(),
    queryFn: async () => (await listContinueWatching(12)).data,
  });
  const savedQuery = useQuery({
    queryKey: videoKeys.saved(),
    queryFn: async () => (await listSavedVideos(12)).data,
  });
  const playlistsQuery = usePlaylistsQuery();

  useFocusEffect(
    useCallback(() => {
      focusedRef.current = true;
      if (onlineManager.isOnline()) {
        refetch();
        void continueQuery.refetch();
        void savedQuery.refetch();
        void playlistsQuery.refetch();
      }
      return () => {
        focusedRef.current = false;
      };
    }, [refetch, continueQuery.refetch, savedQuery.refetch, playlistsQuery.refetch])
  );

  useEffect(() => {
    const busy = items.some((v) =>
      IN_FLIGHT.has(String(v.status || "").toUpperCase())
    );
    if (!busy) return;
    const id = setInterval(() => {
      if (focusedRef.current && onlineManager.isOnline()) refetch();
    }, 2500);
    return () => clearInterval(id);
  }, [items, refetch]);

  const savedIds = useMemo(() => {
    const set = new Set<string>();
    for (const v of savedQuery.data ?? []) set.add(v.upload_id);
    return set;
  }, [savedQuery.data]);

  const listError =
    uploadError || queryErrorText(isError, error, items.length > 0);

  return (
    <Screen>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Library</Text>
          <Text
            style={styles.title}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.75}
          >
            OnStream
          </Text>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Watch history"
          onPress={() => router.push("/library/history" as Href)}
          style={({ pressed }) => [
            styles.iconBtn,
            pressed && { opacity: 0.88 },
          ]}
        >
          <Ionicons name="time-outline" size={22} color={colors.text} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Playlists"
          onPress={() => router.push("/playlist" as Href)}
          style={({ pressed }) => [
            styles.iconBtn,
            pressed && { opacity: 0.88 },
          ]}
        >
          <Ionicons name="list-outline" size={22} color={colors.text} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Search"
          onPress={() => router.push("/search")}
          style={({ pressed }) => [
            styles.iconBtn,
            pressed && { opacity: 0.88 },
          ]}
        >
          <Ionicons name="search" size={22} color={colors.text} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Add video"
          onPress={() => {
            setUploadError(null);
            setComposerOpen(true);
          }}
          style={({ pressed }) => [
            styles.addBtn,
            pressed && { opacity: 0.88, transform: [{ scale: 0.97 }] },
          ]}
        >
          <Ionicons name="add" size={26} color={colors.bg} />
        </Pressable>
      </View>

      {listError ? <Text style={styles.error}>{listError}</Text> : null}

      {isPending && items.length === 0 ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ElasticRefreshFlatList
          data={items}
          keyExtractor={(item) => item.upload_id}
          contentContainerStyle={[
            styles.list,
            items.length === 0 && styles.listEmpty,
          ]}
          onRefresh={async () => {
            await Promise.all([
              refetch(),
              continueQuery.refetch(),
              savedQuery.refetch(),
              playlistsQuery.refetch(),
            ]);
          }}
          ListHeaderComponent={
            <LibraryShelves
              continueItems={continueQuery.data ?? []}
              savedItems={savedQuery.data ?? []}
              playlists={playlistsQuery.data ?? []}
            />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Ionicons
                  name="film-outline"
                  size={32}
                  color={colors.brand}
                />
              </View>
              <Text style={styles.emptyKicker}>First run</Text>
              <Text style={styles.emptyTitle}>Your library is empty</Text>
              <Text style={styles.emptyBody}>
                Upload a short clip to exercise ABR encode, playback tokens,
                captions, and continue watching.
              </Text>
              <View style={styles.emptySteps}>
                <Text style={styles.emptyStep}>1. Add a video (Quick or Resumable)</Text>
                <Text style={styles.emptyStep}>2. Wait until status is READY</Text>
                <Text style={styles.emptyStep}>3. Play — progress shows up under Continue</Text>
              </View>
              <Pressable
                onPress={() => {
                  setUploadError(null);
                  setComposerOpen(true);
                }}
                style={({ pressed }) => [
                  styles.emptyCta,
                  pressed && { opacity: 0.9, transform: [{ scale: 0.98 }] },
                ]}
              >
                <Ionicons name="add-circle" size={18} color={colors.bg} />
                <Text style={styles.emptyCtaText}>Add your first video</Text>
              </Pressable>
              <Pressable
                onPress={() => router.push("/(tabs)/settings" as Href)}
                style={({ pressed }) => [
                  styles.emptySecondary,
                  pressed && { opacity: 0.8 },
                ]}
              >
                <Text style={styles.emptySecondaryText}>
                  Or open Lab for browser upload tools
                </Text>
                <Ionicons
                  name="chevron-forward"
                  size={16}
                  color={colors.brand}
                />
              </Pressable>
            </View>
          }
          renderItem={({ item }) => {
            const hint = videoPipelineHint(item);
            const status = String(item.status || "").toUpperCase();
            return (
              <Pressable
                onPressIn={() => {
                  prefetchVideo(qc, item.upload_id);
                }}
                onPress={() => router.push(`/video/${item.upload_id}`)}
                style={({ pressed }) => [
                  styles.card,
                  pressed && { opacity: 0.9 },
                ]}
              >
                <View style={styles.cardTop}>
                  <View style={styles.iconWrap}>
                    <Ionicons
                      name={
                        status === "READY"
                          ? "play-circle"
                          : status === "ERROR"
                            ? "alert-circle"
                            : status === "QUARANTINED"
                              ? "shield-half-outline"
                              : "hourglass-outline"
                      }
                      size={22}
                      color={
                        status === "READY"
                          ? colors.brand
                          : status === "ERROR"
                            ? colors.danger
                            : status === "QUARANTINED"
                              ? colors.warning
                              : colors.textMuted
                      }
                    />
                  </View>
                  <Text style={styles.cardTitle} numberOfLines={1}>
                    {item.title}
                  </Text>
                  {savedIds.has(item.upload_id) ? (
                    <Ionicons name="heart" size={16} color={colors.live} />
                  ) : null}
                  <StatusPill status={item.status} />
                </View>
                {item.visibility && item.visibility !== "private" ? (
                  <Text style={styles.meta}>
                    {item.visibility === "public" ? "Public" : "Unlisted"}
                  </Text>
                ) : null}
                <Text style={[styles.hint, { color: HINT_COLOR[hint.tone] }]}>
                  {hint.text}
                </Text>
                <View style={styles.metaRow}>
                  <Ionicons
                    name="finger-print-outline"
                    size={12}
                    color={colors.textDim}
                  />
                  <Text style={styles.meta}>{item.upload_id}</Text>
                </View>
                {item.quality_score != null ? (
                  <View style={styles.metaRow}>
                    <Ionicons
                      name="analytics-outline"
                      size={12}
                      color={colors.textDim}
                    />
                    <Text style={styles.meta}>
                      Quality {item.quality_score.toFixed(1)}
                    </Text>
                  </View>
                ) : null}
                {item.caption_vtt_path ? (
                  <View style={styles.metaRow}>
                    <Ionicons
                      name="text-outline"
                      size={12}
                      color={colors.brandDim}
                    />
                    <Text style={[styles.meta, { color: colors.brandDim }]}>
                      Captions ready
                    </Text>
                  </View>
                ) : null}
              </Pressable>
            );
          }}
        />
      )}

      <VideoUploadComposer
        visible={composerOpen}
        onClose={() => setComposerOpen(false)}
        onFinished={async () => {
          setUploadError(null);
          await qc.invalidateQueries({ queryKey: videoKeys.list() });
        }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  addBtn: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
    borderRadius: radii.lg,
  },
  iconBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  kicker: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: {
    color: colors.brand,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 32,
    letterSpacing: -0.8,
    flexShrink: 1,
  },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: 40,
    gap: 12,
  },
  listEmpty: {
    flexGrow: 1,
  },
  card: {
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 16,
    gap: 6,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  iconWrap: {
    width: 28,
    alignItems: "center",
  },
  cardTitle: {
    flex: 1,
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  hint: {
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
    lineHeight: 18,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  empty: {
    paddingVertical: 28,
    paddingHorizontal: 4,
    gap: 10,
    alignItems: "flex-start",
  },
  emptyIcon: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: colors.brandSoft,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
  },
  emptyKicker: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  emptyTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 26,
    letterSpacing: -0.4,
  },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  emptySteps: {
    marginTop: 4,
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    alignSelf: "stretch",
  },
  emptyStep: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
    lineHeight: 18,
  },
  emptyCta: {
    marginTop: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.brand,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: radii.md,
  },
  emptyCtaText: {
    color: colors.bg,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  emptySecondary: {
    marginTop: 4,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  emptySecondaryText: {
    color: colors.brand,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: 8,
    fontFamily: "DMSans_500Medium",
  },
});
