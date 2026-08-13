import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { Stack, useRouter, type Href } from "expo-router";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "@/api/client";
import { createPlaylist, deletePlaylist } from "@/api/playlists";
import { Button } from "@/components/Button";
import { CinemaSheet } from "@/components/CinemaSheet";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Field } from "@/components/Field";
import { PlaylistArt } from "@/components/PlaylistArt";
import { Screen } from "@/components/Screen";
import { toast } from "@/lib/toast";
import { playlistKeys } from "@/query/keys";
import { usePlaylistsQuery } from "@/query/playlists";
import { colors, radii, spacing } from "@/theme/tokens";

export default function PlaylistIndexScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: items = [], isPending, refetch } = usePlaylistsQuery();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const closeSheet = () => {
    if (busy) return;
    setOpen(false);
    setError(null);
  };

  const create = async () => {
    const n = name.trim();
    if (n.length < 1) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await createPlaylist(n, isPublic);
      setOpen(false);
      setName("");
      setIsPublic(false);
      await qc.invalidateQueries({ queryKey: playlistKeys.list() });
      toast.success(`Created ${n}`);
      router.push(`/playlist/${res.data.id}` as Href);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create playlist");
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = (id: number, title: string) => {
    Alert.alert(
      "Delete playlist?",
      `Permanently delete “${title}”. Videos stay in your library.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            void (async () => {
              try {
                await deletePlaylist(id);
                await qc.invalidateQueries({ queryKey: playlistKeys.list() });
                toast.success("Playlist deleted.");
              } catch (e) {
                toast.error(
                  e instanceof ApiError ? e.message : "Delete failed"
                );
              }
            })();
          },
        },
      ]
    );
  };

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: "Playlists",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
          headerShadowVisible: false,
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="New playlist"
              onPress={() => setOpen(true)}
              hitSlop={8}
              style={{ marginRight: 8 }}
            >
              <Ionicons name="add" size={24} color={colors.brand} />
            </Pressable>
          ),
        }}
      />
      {isPending && items.length === 0 ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ElasticRefreshFlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={[
            styles.list,
            items.length === 0 && styles.listEmpty,
          ]}
          onRefresh={async () => {
            await refetch();
          }}
          ListHeaderComponent={
            items.length > 0 ? (
              <Text style={styles.count}>
                {items.length} playlist{items.length === 1 ? "" : "s"}
              </Text>
            ) : null
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Ionicons name="albums-outline" size={32} color={colors.brand} />
              </View>
              <Text style={styles.emptyKicker}>Collect</Text>
              <Text style={styles.emptyTitle}>No playlists yet</Text>
              <Text style={styles.emptyBody}>
                Group videos into an ordered list, play them in sequence, and
                optionally publish an RSS feed.
              </Text>
              <Pressable
                onPress={() => setOpen(true)}
                style={({ pressed }) => [
                  styles.emptyCta,
                  pressed && { opacity: 0.9, transform: [{ scale: 0.98 }] },
                ]}
              >
                <Ionicons name="add-circle" size={18} color={colors.bg} />
                <Text style={styles.emptyCtaText}>New playlist</Text>
              </Pressable>
            </View>
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push(`/playlist/${item.id}` as Href)}
              onLongPress={() => confirmDelete(item.id, item.name)}
              style={({ pressed }) => [
                styles.card,
                pressed && { opacity: 0.9 },
              ]}
            >
              <PlaylistArt size="sm" isPublic={item.is_public} />
              <View style={styles.cardCopy}>
                <Text style={styles.cardTitle} numberOfLines={1}>
                  {item.name}
                </Text>
                <View style={styles.metaRow}>
                  <Ionicons
                    name={
                      item.is_public ? "globe-outline" : "lock-closed-outline"
                    }
                    size={12}
                    color={colors.textDim}
                  />
                  <Text style={styles.meta}>
                    {item.is_public ? "Public" : "Private"}
                  </Text>
                </View>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Playlist options"
                hitSlop={8}
                onPress={() => confirmDelete(item.id, item.name)}
                style={({ pressed }) => [
                  styles.moreBtn,
                  pressed && { opacity: 0.7 },
                ]}
              >
                <Ionicons
                  name="ellipsis-horizontal"
                  size={18}
                  color={colors.textDim}
                />
              </Pressable>
            </Pressable>
          )}
        />
      )}
      <CinemaSheet
        visible={open}
        onClose={closeSheet}
        dismissEnabled={!busy}
      >
        <Text style={styles.sheetTitle}>New playlist</Text>
        <Field
          label="Name"
          value={name}
          onChangeText={setName}
          autoCapitalize="sentences"
          maxLength={100}
        />
        <Pressable
          onPress={() => setIsPublic((v) => !v)}
          style={({ pressed }) => [
            styles.privacy,
            isPublic && styles.privacyOn,
            pressed && { opacity: 0.9 },
          ]}
        >
          <View style={styles.privacyIcon}>
            <Ionicons
              name={isPublic ? "globe-outline" : "lock-closed-outline"}
              size={18}
              color={isPublic ? colors.brand : colors.textMuted}
            />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.privacyTitle}>
              {isPublic ? "Public" : "Private"}
            </Text>
            <Text style={styles.privacyHint}>
              {isPublic
                ? "Listed on your RSS feed. Anyone with the link can read it."
                : "Only you can see this playlist."}
            </Text>
          </View>
        </Pressable>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button label="Create" loading={busy} onPress={() => void create()} />
      </CinemaSheet>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.lg, gap: 10, paddingBottom: 40 },
  listEmpty: { flexGrow: 1, justifyContent: "center" },
  count: {
    color: colors.textDim,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    letterSpacing: 0.4,
    textTransform: "uppercase",
    marginBottom: 2,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
    paddingLeft: 10,
    paddingRight: 6,
    borderRadius: radii.lg,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  cardCopy: { flex: 1, gap: 4 },
  cardTitle: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 16,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  moreBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  empty: {
    alignItems: "center",
    gap: 10,
    paddingHorizontal: spacing.xl,
  },
  emptyIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
    marginBottom: 4,
  },
  emptyKicker: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
    letterSpacing: 1.4,
    textTransform: "uppercase",
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
    textAlign: "center",
  },
  emptyCta: {
    marginTop: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.brand,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: radii.md,
  },
  emptyCtaText: {
    color: colors.bg,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  sheetTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
    marginBottom: 8,
  },
  privacy: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  privacyOn: {
    borderColor: "rgba(46, 230, 166, 0.35)",
    backgroundColor: colors.brandSoft,
  },
  privacyIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bgElevated,
  },
  privacyTitle: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 14,
  },
  privacyHint: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    lineHeight: 16,
  },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
});
