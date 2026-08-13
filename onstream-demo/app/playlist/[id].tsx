import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import * as Clipboard from "expo-clipboard";
import { Stack, useLocalSearchParams, useRouter, type Href } from "expo-router";
import React, { useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getApiBase, userFacingError } from "@/api/client";
import {
  deletePlaylist,
  removeVideoFromPlaylist,
  updatePlaylist,
  updatePlaylistVideoPosition,
  type PlaylistVideo,
} from "@/api/playlists";
import { Button } from "@/components/Button";
import { CinemaSheet } from "@/components/CinemaSheet";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Field } from "@/components/Field";
import { PlaylistArt } from "@/components/PlaylistArt";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { toast } from "@/lib/toast";
import { playlistKeys } from "@/query/keys";
import { usePlaylistQuery, usePlaylistVideosQuery } from "@/query/playlists";
import { colors, radii, spacing } from "@/theme/tokens";

function formatClock(seconds?: number | null) {
  if (seconds == null || seconds <= 0) return null;
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

function formatTotal(seconds: number) {
  if (seconds <= 0) return null;
  const m = Math.round(seconds / 60);
  if (m < 1) return `${Math.floor(seconds)}s`;
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
}

export default function PlaylistDetailScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const pid = Number(id);
  const valid = Number.isFinite(pid);
  const router = useRouter();
  const qc = useQueryClient();
  const { username } = useAuth();
  const playlistQuery = usePlaylistQuery(valid ? pid : undefined);
  const videosQuery = usePlaylistVideosQuery(valid ? pid : undefined);
  const playlist = playlistQuery.data;
  const items = videosQuery.data ?? [];
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [rename, setRename] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const pendingRename = useRef(false);

  const feedUrl =
    playlist?.is_public && username
      ? `${getApiBase()}/v1/feeds/${encodeURIComponent(username)}/playlists/${pid}.rss`
      : null;

  const totalLabel = useMemo(() => {
    const sec = items.reduce((n, v) => n + (v.duration || 0), 0);
    return formatTotal(sec);
  }, [items]);

  const invalidate = async () => {
    await qc.invalidateQueries({ queryKey: playlistKeys.detail(pid) });
    await qc.invalidateQueries({ queryKey: playlistKeys.videos(pid) });
    await qc.invalidateQueries({ queryKey: playlistKeys.list() });
  };

  const playAll = () => {
    const first =
      items.find((v) => String(v.status || "").toUpperCase() === "READY") ||
      items[0];
    if (!first) {
      toast.info("Add a video from its detail screen.");
      return;
    }
    router.push(
      `/video/${first.upload_id}?playlist=${pid}&play=1` as Href
    );
  };

  const togglePublic = async () => {
    if (!playlist || busy) return;
    const next = !playlist.is_public;
    setBusy(true);
    try {
      await updatePlaylist(pid, { is_public: next });
      await invalidate();
      toast.success(next ? "Playlist is public." : "Playlist is private.");
    } catch (e) {
      toast.error(userFacingError(e, "Could not update visibility"));
    } finally {
      setBusy(false);
    }
  };

  const copyRss = async () => {
    if (!feedUrl) return;
    await Clipboard.setStringAsync(feedUrl);
    toast.success("RSS feed copied.");
  };

  const confirmDelete = () => {
    Alert.alert(
      "Delete playlist?",
      `Permanently delete “${playlist?.name}”. Videos stay in your library.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            void (async () => {
              setBusy(true);
              try {
                await deletePlaylist(pid);
                await qc.invalidateQueries({ queryKey: playlistKeys.list() });
                toast.success("Playlist deleted.");
                router.back();
              } catch (e) {
                toast.error(userFacingError(e, "Delete failed"));
              } finally {
                setBusy(false);
              }
            })();
          },
        },
      ]
    );
  };

  const openRename = () => {
    pendingRename.current = true;
    setMoreOpen(false);
  };

  const saveRename = async () => {
    const n = rename.trim();
    if (n.length < 1) {
      setRenameError("Name is required.");
      return;
    }
    setBusy(true);
    setRenameError(null);
    try {
      await updatePlaylist(pid, { name: n });
      setRenameOpen(false);
      await invalidate();
      toast.success("Playlist renamed.");
    } catch (e) {
      setRenameError(userFacingError(e, "Could not rename"));
    } finally {
      setBusy(false);
    }
  };

  const move = async (index: number, dir: -1 | 1) => {
    const nextIndex = index + dir;
    if (nextIndex < 0 || nextIndex >= items.length || busy) return;
    const a = items[index];
    const b = items[nextIndex];
    const next = items.map((row, i) => {
      if (i === index) return { ...b, position: index };
      if (i === nextIndex) return { ...a, position: nextIndex };
      return row;
    });
    qc.setQueryData<PlaylistVideo[]>(playlistKeys.videos(pid), next);
    setBusy(true);
    try {
      await Promise.all([
        updatePlaylistVideoPosition(pid, a.upload_id, nextIndex),
        updatePlaylistVideoPosition(pid, b.upload_id, index),
      ]);
    } catch (e) {
      await videosQuery.refetch();
      toast.error(userFacingError(e, "Could not reorder"));
    } finally {
      setBusy(false);
    }
  };

  const removeItem = (item: PlaylistVideo) => {
    Alert.alert("Remove from playlist?", `Take “${item.title}” out of this list.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: () => {
          void (async () => {
            const prev = items;
            qc.setQueryData<PlaylistVideo[]>(
              playlistKeys.videos(pid),
              items.filter((row) => row.upload_id !== item.upload_id)
            );
            try {
              await removeVideoFromPlaylist(pid, item.upload_id);
              await qc.invalidateQueries({ queryKey: playlistKeys.list() });
              toast.success(`Removed ${item.title}`);
            } catch (e) {
              qc.setQueryData(playlistKeys.videos(pid), prev);
              toast.error(userFacingError(e, "Could not remove"));
            }
          })();
        },
      },
    ]);
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
          headerShadowVisible: false,
          headerRight: () =>
            playlist ? (
              <View style={styles.headerBtns}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={
                    editing ? "Done reordering" : "Reorder videos"
                  }
                  hitSlop={8}
                  onPress={() => setEditing((v) => !v)}
                  style={({ pressed }) => [
                    styles.headerBtn,
                    editing && styles.headerBtnOn,
                    pressed && { opacity: 0.75 },
                  ]}
                >
                  <Ionicons
                    name="swap-vertical"
                    size={20}
                    color={editing ? colors.bg : colors.text}
                  />
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Playlist options"
                  hitSlop={8}
                  onPress={() => setMoreOpen(true)}
                  style={({ pressed }) => [
                    styles.headerBtn,
                    pressed && { opacity: 0.75 },
                  ]}
                >
                  <Ionicons
                    name="ellipsis-horizontal"
                    size={20}
                    color={colors.text}
                  />
                </Pressable>
              </View>
            ) : null,
        }}
      />
      {playlistQuery.isPending && !playlist ? (
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
            await Promise.all([playlistQuery.refetch(), videosQuery.refetch()]);
          }}
          ListHeaderComponent={
            <View style={styles.head}>
              <View style={styles.artWrap}>
                <PlaylistArt size="lg" isPublic={Boolean(playlist?.is_public)} />
              </View>
              <Text style={styles.title}>{playlist?.name}</Text>
              <View style={styles.metaRow}>
                <Ionicons
                  name={
                    playlist?.is_public ? "globe-outline" : "lock-closed-outline"
                  }
                  size={14}
                  color={colors.textMuted}
                />
                <Text style={styles.meta}>
                  {playlist?.is_public ? "Public" : "Private"}
                  {" · "}
                  {items.length} video{items.length === 1 ? "" : "s"}
                  {totalLabel ? ` · ${totalLabel}` : ""}
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Play all"
                disabled={items.length === 0}
                onPress={playAll}
                style={({ pressed }) => [
                  styles.playAll,
                  items.length === 0 && { opacity: 0.4 },
                  pressed && items.length > 0 && { opacity: 0.88 },
                ]}
              >
                <Ionicons name="play" size={18} color={colors.bg} />
                <Text style={styles.playAllText}>Play all</Text>
              </Pressable>
              {editing ? (
                <Text style={styles.editHint}>
                  Use the arrows to change order. Tap the header icon when done.
                </Text>
              ) : null}
            </View>
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Ionicons
                  name="film-outline"
                  size={28}
                  color={colors.brand}
                />
              </View>
              <Text style={styles.emptyTitle}>Nothing in this list yet</Text>
              <Text style={styles.emptyBody}>
                Open a video and tap Add to playlist. Order is yours to rearrange.
              </Text>
            </View>
          }
          renderItem={({ item, index }) => {
            const clock = formatClock(item.duration);
            const status = String(item.status || "").toUpperCase();
            const ready = status === "READY" || !status;
            return (
              <View style={styles.row}>
                <Pressable
                  onPress={() =>
                    router.push(
                      `/video/${item.upload_id}?playlist=${pid}&play=1` as Href
                    )
                  }
                  style={({ pressed }) => [
                    styles.rowMain,
                    pressed && { opacity: 0.88 },
                  ]}
                >
                  <Text style={styles.index}>{index + 1}</Text>
                  <View style={styles.thumb}>
                    <Ionicons
                      name={ready ? "play" : "hourglass-outline"}
                      size={18}
                      color={ready ? colors.brand : colors.textMuted}
                    />
                  </View>
                  <View style={styles.rowCopy}>
                    <Text style={styles.rowTitle} numberOfLines={2}>
                      {item.title}
                    </Text>
                    <Text style={styles.rowMeta} numberOfLines={1}>
                      {clock || (ready ? "Ready" : status || "Video")}
                    </Text>
                  </View>
                </Pressable>
                {editing ? (
                  <View style={styles.reorder}>
                    <Pressable
                      accessibilityLabel="Move up"
                      hitSlop={6}
                      disabled={index === 0 || busy}
                      onPress={() => void move(index, -1)}
                      style={({ pressed }) => [
                        styles.reorderBtn,
                        (index === 0 || busy) && { opacity: 0.28 },
                        pressed && { opacity: 0.6 },
                      ]}
                    >
                      <Ionicons
                        name="chevron-up"
                        size={20}
                        color={colors.text}
                      />
                    </Pressable>
                    <Pressable
                      accessibilityLabel="Move down"
                      hitSlop={6}
                      disabled={index >= items.length - 1 || busy}
                      onPress={() => void move(index, 1)}
                      style={({ pressed }) => [
                        styles.reorderBtn,
                        (index >= items.length - 1 || busy) && { opacity: 0.28 },
                        pressed && { opacity: 0.6 },
                      ]}
                    >
                      <Ionicons
                        name="chevron-down"
                        size={20}
                        color={colors.text}
                      />
                    </Pressable>
                  </View>
                ) : (
                  <Pressable
                    accessibilityLabel="Remove from playlist"
                    hitSlop={8}
                    onPress={() => removeItem(item)}
                    style={({ pressed }) => [
                      styles.removeBtn,
                      pressed && { opacity: 0.7 },
                    ]}
                  >
                    <Ionicons
                      name="close-circle"
                      size={22}
                      color={colors.textDim}
                    />
                  </Pressable>
                )}
              </View>
            );
          }}
        />
      )}
      <CinemaSheet
        visible={moreOpen}
        onClose={() => setMoreOpen(false)}
        dismissEnabled={!busy}
        onExited={() => {
          if (!pendingRename.current) return;
          pendingRename.current = false;
          setRename(playlist?.name || "");
          setRenameError(null);
          setRenameOpen(true);
        }}
      >
        <Text style={styles.sheetTitle}>{playlist?.name}</Text>
        <Pressable
          onPress={openRename}
          style={({ pressed }) => [styles.menuRow, pressed && { opacity: 0.8 }]}
        >
          <Ionicons name="pencil-outline" size={18} color={colors.text} />
          <Text style={styles.menuLabel}>Rename</Text>
        </Pressable>
        <Pressable
          onPress={() => {
            setMoreOpen(false);
            void togglePublic();
          }}
          style={({ pressed }) => [styles.menuRow, pressed && { opacity: 0.8 }]}
        >
          <Ionicons
            name={
              playlist?.is_public ? "lock-closed-outline" : "globe-outline"
            }
            size={18}
            color={colors.text}
          />
          <Text style={styles.menuLabel}>
            {playlist?.is_public ? "Make private" : "Make public"}
          </Text>
        </Pressable>
        {feedUrl ? (
          <Pressable
            onPress={() => {
              setMoreOpen(false);
              void copyRss();
            }}
            style={({ pressed }) => [styles.menuRow, pressed && { opacity: 0.8 }]}
          >
            <Ionicons name="logo-rss" size={18} color={colors.text} />
            <Text style={styles.menuLabel}>Copy RSS feed</Text>
          </Pressable>
        ) : null}
        <Pressable
          onPress={() => {
            setMoreOpen(false);
            confirmDelete();
          }}
          style={({ pressed }) => [styles.menuRow, pressed && { opacity: 0.8 }]}
        >
          <Ionicons name="trash-outline" size={18} color={colors.danger} />
          <Text style={[styles.menuLabel, { color: colors.danger }]}>
            Delete playlist
          </Text>
        </Pressable>
      </CinemaSheet>
      <CinemaSheet
        visible={renameOpen}
        onClose={() => setRenameOpen(false)}
        dismissEnabled={!busy}
      >
        <Text style={styles.sheetTitle}>Rename playlist</Text>
        <Field
          label="Name"
          value={rename}
          onChangeText={setRename}
          autoCapitalize="sentences"
          maxLength={100}
        />
        {renameError ? <Text style={styles.error}>{renameError}</Text> : null}
        <Button
          label="Save"
          loading={busy}
          onPress={() => void saveRename()}
        />
      </CinemaSheet>
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerBtns: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginRight: 4,
  },
  headerBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bgSoft,
  },
  headerBtnOn: {
    backgroundColor: colors.brand,
  },
  list: { padding: spacing.lg, gap: 8, paddingBottom: 48 },
  listEmpty: { flexGrow: 1 },
  head: { gap: 12, marginBottom: 12, alignItems: "center" },
  artWrap: { marginBottom: 4 },
  title: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 24,
    textAlign: "center",
    letterSpacing: -0.4,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  meta: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  editHint: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    textAlign: "center",
  },
  playAll: {
    alignSelf: "stretch",
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.brand,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  playAllText: {
    color: colors.bg,
    fontFamily: "DMSans_700Bold",
    fontSize: 16,
  },
  empty: {
    alignItems: "center",
    gap: 10,
    paddingTop: 28,
    paddingHorizontal: spacing.md,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
  },
  emptyTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
    textAlign: "center",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 10,
    paddingLeft: 10,
    paddingRight: 6,
    borderRadius: radii.lg,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  rowMain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  index: {
    width: 22,
    textAlign: "center",
    color: colors.textDim,
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
  },
  thumb: {
    width: 56,
    height: 40,
    borderRadius: radii.sm,
    backgroundColor: colors.bgSoft,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  rowCopy: { flex: 1, gap: 2 },
  rowTitle: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  rowMeta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  reorder: { flexDirection: "row", alignItems: "center" },
  reorderBtn: {
    width: 32,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  removeBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  sheetTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
    marginBottom: 8,
  },
  menuRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    minHeight: 48,
    paddingVertical: 8,
  },
  menuLabel: {
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 16,
  },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
});
