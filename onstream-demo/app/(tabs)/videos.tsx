import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import { useFocusEffect, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError } from "@/api/client";
import { uploadVideoMultipart } from "@/api/videos";
import { Button } from "@/components/Button";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
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
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const focusedRef = useRef(true);

  const {
    data: items = [],
    isPending,
    isError,
    error,
    refetch,
  } = useVideosQuery();

  const [pullRefreshing, setPullRefreshing] = useState(false);

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
        <Button
          label={uploading ? "Uploading…" : "Upload"}
          loading={uploading}
          style={{ minWidth: 110 }}
          onPress={async () => {
            const picked = await DocumentPicker.getDocumentAsync({
              type: "video/*",
              copyToCacheDirectory: true,
            });
            if (picked.canceled || !picked.assets?.[0]) return;
            const asset = picked.assets[0];
            setUploading(true);
            setUploadError(null);
            try {
              await uploadVideoMultipart({
                uri: asset.uri,
                name: asset.name || "upload.mp4",
                mimeType: asset.mimeType || "video/mp4",
                title: (asset.name || "Mobile upload").replace(/\.[^.]+$/, ""),
              });
              await qc.invalidateQueries({ queryKey: videoKeys.list() });
            } catch (e) {
              setUploadError(
                e instanceof ApiError ? e.message : "Upload failed"
              );
            } finally {
              setUploading(false);
            }
          }}
        />
      </View>

      {listError ? <Text style={styles.error}>{listError}</Text> : null}

      {isPending && items.length === 0 ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.upload_id}
          contentContainerStyle={styles.list}
          bounces
          alwaysBounceVertical={false}
          overScrollMode="auto"
          refreshControl={
            <RefreshControl
              refreshing={pullRefreshing}
              tintColor={colors.brand}
              colors={[colors.brand]}
              progressBackgroundColor={colors.bgElevated}
              onRefresh={async () => {
                setPullRefreshing(true);
                try {
                  await refetch();
                } finally {
                  setPullRefreshing(false);
                }
              }}
            />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="film-outline" size={40} color={colors.textDim} />
              <Text style={styles.emptyTitle}>No videos yet</Text>
              <Text style={styles.emptyBody}>
                Upload a clip to exercise ABR, tokens, and HLS playback.
              </Text>
            </View>
          }
          renderItem={({ item }) => {
            const hint = videoPipelineHint(item);
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
                        String(item.status).toUpperCase() === "READY"
                          ? "play-circle"
                          : String(item.status).toUpperCase() === "ERROR"
                            ? "alert-circle"
                            : String(item.status).toUpperCase() ===
                                "QUARANTINED"
                              ? "shield-half-outline"
                              : "hourglass-outline"
                      }
                      size={22}
                      color={
                        String(item.status).toUpperCase() === "READY"
                          ? colors.brand
                          : String(item.status).toUpperCase() === "ERROR"
                            ? colors.danger
                            : String(item.status).toUpperCase() ===
                                "QUARANTINED"
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
                <Text style={styles.meta}>{item.upload_id}</Text>
                {item.quality_score != null ? (
                  <Text style={styles.meta}>
                    Quality {item.quality_score.toFixed(1)}
                  </Text>
                ) : null}
              </Pressable>
            );
          }}
        />
      )}
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
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  empty: { paddingVertical: 48, gap: 8, alignItems: "flex-start" },
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
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: 8,
    fontFamily: "DMSans_500Medium",
  },
});
