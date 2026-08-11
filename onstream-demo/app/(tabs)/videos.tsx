import * as DocumentPicker from "expo-document-picker";
import { useFocusEffect, useRouter } from "expo-router";
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
import { listVideos, uploadVideoMultipart, Video } from "@/api/videos";
import { Button } from "@/components/Button";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { colors, radii, spacing } from "@/theme/tokens";

const IN_FLIGHT = new Set(["PENDING", "PROCESSING", "QUEUED", "UPLOADING"]);

export default function VideosScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [items, setItems] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const focusedRef = useRef(true);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listVideos();
      setItems(res.data || []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load videos");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      focusedRef.current = true;
      load();
      return () => {
        focusedRef.current = false;
      };
    }, [load])
  );

  // Auto-refresh while any video is still processing
  useEffect(() => {
    const busy = items.some((v) =>
      IN_FLIGHT.has(String(v.status || "").toUpperCase())
    );
    if (!busy) return;
    const id = setInterval(() => {
      if (focusedRef.current) load();
    }, 2500);
    return () => clearInterval(id);
  }, [items, load]);

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
            setError(null);
            try {
              await uploadVideoMultipart({
                uri: asset.uri,
                name: asset.name || "upload.mp4",
                mimeType: asset.mimeType || "video/mp4",
                title: (asset.name || "Mobile upload").replace(/\.[^.]+$/, ""),
              });
              await load();
            } catch (e) {
              setError(e instanceof ApiError ? e.message : "Upload failed");
            } finally {
              setUploading(false);
            }
          }}
        />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {loading ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.upload_id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              tintColor={colors.brand}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>No videos yet</Text>
              <Text style={styles.emptyBody}>
                Upload a clip to exercise ABR, tokens, and HLS playback.
              </Text>
            </View>
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push(`/video/${item.upload_id}`)}
              style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}
            >
              <View style={styles.cardTop}>
                <Text style={styles.cardTitle} numberOfLines={1}>
                  {item.title}
                </Text>
                <StatusPill status={item.status} />
              </View>
              <Text style={styles.meta}>{item.upload_id}</Text>
              {item.quality_score != null ? (
                <Text style={styles.meta}>Quality {item.quality_score.toFixed(1)}</Text>
              ) : null}
            </Pressable>
          )}
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
    gap: 8,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  cardTitle: {
    flex: 1,
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  empty: { paddingVertical: 48, gap: 8 },
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
