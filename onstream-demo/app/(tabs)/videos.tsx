import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { VideoUploadComposer } from "@/components/VideoUploadComposer";
import { videoPipelineHint } from "@/lib/videoStatus";
import { videoKeys } from "@/query/keys";
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

  useFocusEffect(
    useCallback(() => {
      focusedRef.current = true;
      refetch();
      return () => {
        focusedRef.current = false;
      };
    }, [refetch])
  );

  useEffect(() => {
    const busy = items.some((v) =>
      IN_FLIGHT.has(String(v.status || "").toUpperCase())
    );
    if (!busy) return;
    const id = setInterval(() => {
      if (focusedRef.current) refetch();
    }, 2500);
    return () => clearInterval(id);
  }, [items, refetch]);

  const listError =
    uploadError ||
    (isError
      ? error instanceof Error
        ? error.message
        : "Failed to load videos"
      : null);

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
          contentContainerStyle={styles.list}
          onRefresh={async () => {
            await refetch();
          }}
          ListEmptyComponent={
            <Pressable
              onPress={() => setComposerOpen(true)}
              style={({ pressed }) => [
                styles.empty,
                pressed && { opacity: 0.9 },
              ]}
            >
              <View style={styles.emptyIcon}>
                <Ionicons
                  name="cloud-upload-outline"
                  size={32}
                  color={colors.brand}
                />
              </View>
              <Text style={styles.emptyTitle}>No videos yet</Text>
              <Text style={styles.emptyBody}>
                Add a clip to exercise ABR, tokens, captions, and HLS — Quick
                multipart or Resumable direct upload.
              </Text>
              <View style={styles.emptyCta}>
                <Ionicons name="add-circle" size={18} color={colors.bg} />
                <Text style={styles.emptyCtaText}>Add video</Text>
              </View>
            </Pressable>
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
                  <StatusPill status={item.status} />
                </View>
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
    paddingVertical: 40,
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
  emptyTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 22,
  },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
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
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: 8,
    fontFamily: "DMSans_500Medium",
  },
});
