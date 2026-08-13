import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import * as Clipboard from "expo-clipboard";
import { Stack, useLocalSearchParams, useRouter, type Href } from "expo-router";
import React from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getApiBase } from "@/api/client";
import {
  deletePlaylist,
  removeVideoFromPlaylist,
  updatePlaylist,
  updatePlaylistVideoPosition,
} from "@/api/playlists";
import { CopyRow } from "@/components/CopyRow";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { playlistKeys } from "@/query/keys";
import { usePlaylistQuery, usePlaylistVideosQuery } from "@/query/playlists";
import { colors, radii, spacing } from "@/theme/tokens";

export default function PlaylistDetailScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const pid = Number(id);
  const router = useRouter();
  const qc = useQueryClient();
  const { username } = useAuth();
  const playlistQuery = usePlaylistQuery(Number.isFinite(pid) ? pid : undefined);
  const videosQuery = usePlaylistVideosQuery(
    Number.isFinite(pid) ? pid : undefined
  );
  const playlist = playlistQuery.data;
  const items = videosQuery.data ?? [];
  const feedUrl =
    playlist?.is_public && username
      ? `${getApiBase()}/v1/feeds/${encodeURIComponent(username)}/playlists/${pid}.rss`
      : null;

  const invalidate = async () => {
    await qc.invalidateQueries({ queryKey: playlistKeys.detail(pid) });
    await qc.invalidateQueries({ queryKey: playlistKeys.videos(pid) });
    await qc.invalidateQueries({ queryKey: playlistKeys.list() });
  };

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: playlist?.name || "Playlist",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />
      {playlistQuery.isPending && !playlist ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ElasticRefreshFlatList
          data={items}
          keyExtractor={(item) => item.upload_id}
          contentContainerStyle={styles.list}
          onRefresh={async () => {
            await Promise.all([playlistQuery.refetch(), videosQuery.refetch()]);
          }}
          ListHeaderComponent={
            <View style={styles.head}>
              <Text style={styles.title}>{playlist?.name}</Text>
              <Text style={styles.meta}>
                {items.length} video{items.length === 1 ? "" : "s"} ·{" "}
                {playlist?.is_public ? "Public" : "Private"}
              </Text>
              <View style={styles.actions}>
                <Pressable
                  onPress={() => {
                    void updatePlaylist(pid, {
                      is_public: !playlist?.is_public,
                    }).then(invalidate);
                  }}
                  style={styles.chip}
                >
                  <Text style={styles.chipText}>
                    {playlist?.is_public ? "Make private" : "Make public"}
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => {
                    Alert.alert("Delete playlist?", playlist?.name, [
                      { text: "Cancel", style: "cancel" },
                      {
                        text: "Delete",
                        style: "destructive",
                        onPress: () => {
                          void deletePlaylist(pid).then(() => {
                            void qc.invalidateQueries({
                              queryKey: playlistKeys.list(),
                            });
                            router.back();
                          });
                        },
                      },
                    ]);
                  }}
                  style={styles.chipDanger}
                >
                  <Text style={styles.chipDangerText}>Delete</Text>
                </Pressable>
              </View>
              {feedUrl ? <CopyRow label="RSS feed" value={feedUrl} /> : null}
            </View>
          }
          ListEmptyComponent={
            <Text style={styles.empty}>
              No videos yet. Add from a video’s detail screen.
            </Text>
          }
          renderItem={({ item, index }) => (
            <View style={styles.row}>
              <Pressable
                onPress={() =>
                  router.push(
                    `/video/${item.upload_id}?playlist=${pid}&play=1` as Href
                  )
                }
                style={{ flex: 1, gap: 2 }}
              >
                <Text style={styles.rowTitle}>
                  {index + 1}. {item.title}
                </Text>
                <Text style={styles.rowMeta}>{item.upload_id}</Text>
              </Pressable>
              <Pressable
                onPress={() => {
                  if (index === 0) return;
                  const prev = items[index - 1];
                  void Promise.all([
                    updatePlaylistVideoPosition(pid, item.upload_id, index - 1),
                    updatePlaylistVideoPosition(pid, prev.upload_id, index),
                  ]).then(invalidate);
                }}
                hitSlop={8}
              >
                <Ionicons name="chevron-up" size={20} color={colors.textMuted} />
              </Pressable>
              <Pressable
                onPress={() => {
                  if (index >= items.length - 1) return;
                  const next = items[index + 1];
                  void Promise.all([
                    updatePlaylistVideoPosition(pid, item.upload_id, index + 1),
                    updatePlaylistVideoPosition(pid, next.upload_id, index),
                  ]).then(invalidate);
                }}
                hitSlop={8}
              >
                <Ionicons
                  name="chevron-down"
                  size={20}
                  color={colors.textMuted}
                />
              </Pressable>
              <Pressable
                onPress={() => {
                  void removeVideoFromPlaylist(pid, item.upload_id).then(
                    invalidate
                  );
                }}
                hitSlop={8}
              >
                <Ionicons name="close" size={20} color={colors.danger} />
              </Pressable>
            </View>
          )}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.lg, gap: 8, paddingBottom: 48 },
  head: { gap: 10, marginBottom: 8 },
  title: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 24,
  },
  meta: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  actions: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radii.xl,
    backgroundColor: colors.brandSoft,
  },
  chipText: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
  },
  chipDanger: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radii.xl,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  chipDangerText: {
    color: colors.danger,
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
  },
  empty: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    marginTop: 16,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderRadius: radii.md,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  rowTitle: {
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 15,
  },
  rowMeta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 11,
  },
});

