import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stack, useLocalSearchParams, useRouter, type Href } from "expo-router";
import React, { useCallback, useMemo } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  clearSavedVideos,
  listSavedVideos,
  unfavoriteVideo,
} from "@/api/favorites";
import {
  clearContinueWatching,
  clearWatchHistory,
  clearWatchProgress,
  dismissContinueItem,
  listContinueWatching,
  listWatchHistory,
  type ContinueItem,
} from "@/api/watch";
import type { Video } from "@/api/videos";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { videoKeys } from "@/query/keys";
import { colors, radii, spacing } from "@/theme/tokens";

type Kind = "continue" | "saved" | "history";

const META: Record<
  Kind,
  {
    title: string;
    empty: string;
    icon: keyof typeof Ionicons.glyphMap;
    clearLabel: string;
    clearTitle: string;
    clearBody: string;
  }
> = {
  continue: {
    title: "Continue watching",
    empty: "Nothing in progress — play a video past a few seconds.",
    icon: "play-circle-outline",
    clearLabel: "Clear all",
    clearTitle: "Clear continue watching?",
    clearBody:
      "Hides in-progress items from Continue. Watch history is kept.",
  },
  saved: {
    title: "Saved",
    empty: "Heart a video on its detail screen to save it here.",
    icon: "heart-outline",
    clearLabel: "Clear all",
    clearTitle: "Clear saved?",
    clearBody: "Removes every video from Saved. You can heart them again later.",
  },
  history: {
    title: "Watch history",
    empty: "Watched videos will show up here.",
    icon: "time-outline",
    clearLabel: "Clear all",
    clearTitle: "Clear watch history?",
    clearBody:
      "Permanently removes all resume positions and history, including Continue watching.",
  },
};

function isKind(v: string | undefined): v is Kind {
  return v === "continue" || v === "saved" || v === "history";
}

function formatRemain(pos: number, dur?: number | null) {
  if (!dur || dur <= 0) return null;
  const left = Math.max(0, Math.round(dur - pos));
  const m = Math.floor(left / 60);
  const s = left % 60;
  return `${m}:${s.toString().padStart(2, "0")} left`;
}

type Row =
  | { type: "continue"; item: ContinueItem }
  | { type: "video"; item: Video };

export default function LibraryShelfScreen() {
  const { kind: raw } = useLocalSearchParams<{ kind?: string }>();
  const kind: Kind = isKind(raw) ? raw : "saved";
  const meta = META[kind];
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();

  const continueQuery = useQuery({
    queryKey: videoKeys.continue(),
    queryFn: async () => (await listContinueWatching(50)).data,
    enabled: kind === "continue",
  });
  const savedQuery = useQuery({
    queryKey: videoKeys.saved(),
    queryFn: async () => (await listSavedVideos(100)).data,
    enabled: kind === "saved",
  });
  const historyQuery = useQuery({
    queryKey: videoKeys.history(),
    queryFn: async () => (await listWatchHistory(100)).data,
    enabled: kind === "history",
  });

  const rows: Row[] = useMemo(() => {
    if (kind === "continue") {
      return (continueQuery.data ?? []).map((item) => ({
        type: "continue" as const,
        item,
      }));
    }
    if (kind === "saved") {
      return (savedQuery.data ?? []).map((item) => ({
        type: "video" as const,
        item,
      }));
    }
    return (historyQuery.data ?? []).map((item) => ({
      type: "continue" as const,
      item,
    }));
  }, [kind, continueQuery.data, savedQuery.data, historyQuery.data]);

  const loading =
    (kind === "continue" && continueQuery.isPending) ||
    (kind === "saved" && savedQuery.isPending) ||
    (kind === "history" && historyQuery.isPending);

  const invalidateEngagement = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: videoKeys.continue() }),
      qc.invalidateQueries({ queryKey: videoKeys.history() }),
      qc.invalidateQueries({ queryKey: videoKeys.saved() }),
    ]);
  }, [qc]);

  const removeOne = useMutation({
    mutationFn: async (uploadId: string) => {
      if (kind === "saved") {
        await unfavoriteVideo(uploadId);
      } else if (kind === "continue") {
        await dismissContinueItem(uploadId);
      } else {
        await clearWatchProgress(uploadId);
      }
    },
    onSuccess: () => {
      void invalidateEngagement();
    },
  });

  const clearAll = useMutation({
    mutationFn: async () => {
      if (kind === "continue") await clearContinueWatching();
      else if (kind === "saved") await clearSavedVideos();
      else await clearWatchHistory();
    },
    onSuccess: () => {
      void invalidateEngagement();
    },
  });

  const confirmClearAll = useCallback(() => {
    if (rows.length === 0 || clearAll.isPending) return;
    Alert.alert(meta.clearTitle, meta.clearBody, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Clear",
        style: "destructive",
        onPress: () => clearAll.mutate(),
      },
    ]);
  }, [rows.length, clearAll, meta.clearTitle, meta.clearBody]);

  const confirmRemove = useCallback(
    (uploadId: string, title: string) => {
      const titleText =
        kind === "saved"
          ? "Remove from Saved?"
          : kind === "continue"
            ? "Remove from Continue?"
            : "Remove from history?";
      const body =
        kind === "saved"
          ? `Unheart “${title}”.`
          : kind === "continue"
            ? `Hides “${title}” from Continue. It stays in Watch history.`
            : `Clears resume progress for “${title}”.`;
      Alert.alert(titleText, body, [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: () => removeOne.mutate(uploadId),
        },
      ]);
    },
    [kind, removeOne]
  );

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: meta.title,
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
          headerShadowVisible: false,
          headerRight: () =>
            rows.length > 0 ? (
              <Pressable
                onPress={confirmClearAll}
                hitSlop={10}
                disabled={clearAll.isPending}
                style={({ pressed }) => pressed && { opacity: 0.7 }}
              >
                <Text style={styles.clearHeader}>{meta.clearLabel}</Text>
              </Pressable>
            ) : null,
        }}
      />
      {loading ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 48 }} />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(row) => row.item.upload_id}
          contentContainerStyle={[
            styles.list,
            { paddingBottom: insets.bottom + 32 },
            rows.length === 0 && styles.listEmpty,
          ]}
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Ionicons name={meta.icon} size={28} color={colors.brand} />
              </View>
              <Text style={styles.emptyTitle}>{meta.title}</Text>
              <Text style={styles.emptyBody}>{meta.empty}</Text>
            </View>
          }
          renderItem={({ item: row }) => {
            if (row.type === "video") {
              const v = row.item;
              return (
                <View style={styles.card}>
                  <Pressable
                    onPress={() =>
                      router.push(`/video/${v.upload_id}` as Href)
                    }
                    style={({ pressed }) => [
                      styles.cardMain,
                      pressed && { opacity: 0.9 },
                    ]}
                  >
                    <View style={[styles.thumb, styles.thumbSaved]}>
                      <Ionicons name="heart" size={22} color={colors.live} />
                    </View>
                    <View style={styles.meta}>
                      <Text style={styles.cardTitle} numberOfLines={2}>
                        {v.title}
                      </Text>
                      <StatusPill status={v.status} />
                    </View>
                  </Pressable>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Remove from Saved"
                    hitSlop={8}
                    onPress={() => confirmRemove(v.upload_id, v.title)}
                    style={({ pressed }) => [
                      styles.clearBtn,
                      pressed && { opacity: 0.75 },
                    ]}
                  >
                    <Ionicons
                      name="close-circle"
                      size={22}
                      color={colors.textDim}
                    />
                  </Pressable>
                </View>
              );
            }
            const c = row.item;
            const remain = formatRemain(c.position_seconds, c.duration_seconds);
            return (
              <View style={styles.card}>
                <Pressable
                  onPress={() =>
                    router.push(
                      `/video/${c.upload_id}?play=1` as Href
                    )
                  }
                  style={({ pressed }) => [
                    styles.cardMain,
                    pressed && { opacity: 0.9 },
                  ]}
                >
                  <View style={styles.thumb}>
                    <Ionicons
                      name={c.completed ? "checkmark-circle" : "play"}
                      size={22}
                      color={colors.brand}
                    />
                    {!c.completed ? (
                      <View style={styles.progressTrack}>
                        <View
                          style={[
                            styles.progressFill,
                            {
                              width: `${Math.round(
                                Math.min(1, c.progress_ratio) * 100
                              )}%`,
                            },
                          ]}
                        />
                      </View>
                    ) : null}
                  </View>
                  <View style={styles.meta}>
                    <Text style={styles.cardTitle} numberOfLines={2}>
                      {c.title}
                    </Text>
                    <Text style={styles.cardSub}>
                      {c.completed ? "Completed" : remain || "In progress"}
                    </Text>
                  </View>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Remove from list"
                  hitSlop={8}
                  onPress={() => confirmRemove(c.upload_id, c.title)}
                  style={({ pressed }) => [
                    styles.clearBtn,
                    pressed && { opacity: 0.75 },
                  ]}
                >
                  <Ionicons
                    name="close-circle"
                    size={22}
                    color={colors.textDim}
                  />
                </Pressable>
              </View>
            );
          }}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  clearHeader: {
    color: colors.danger,
    fontFamily: "DMSans_700Bold",
    fontSize: 14,
    paddingHorizontal: 4,
  },
  list: {
    padding: spacing.lg,
    gap: 10,
  },
  listEmpty: { flexGrow: 1, justifyContent: "center" },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 12,
    paddingLeft: 12,
    paddingRight: 8,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  cardMain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  clearBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  thumb: {
    width: 64,
    height: 48,
    borderRadius: radii.sm,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  thumbSaved: {
    backgroundColor: "rgba(255,77,106,0.08)",
    borderColor: "rgba(255,77,106,0.25)",
  },
  progressTrack: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 3,
    backgroundColor: "rgba(255,255,255,0.12)",
  },
  progressFill: {
    height: "100%",
    backgroundColor: colors.brand,
  },
  meta: { flex: 1, gap: 6 },
  cardTitle: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  cardSub: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  empty: {
    alignItems: "center",
    gap: 10,
    paddingHorizontal: spacing.xl,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
    marginBottom: 4,
  },
  emptyTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
  },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
    textAlign: "center",
  },
});
