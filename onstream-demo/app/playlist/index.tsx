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
import { Screen } from "@/components/Screen";
import { playlistKeys } from "@/query/keys";
import { usePlaylistsQuery } from "@/query/playlists";
import { colors, radii, spacing } from "@/theme/tokens";

export default function PlaylistIndexScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: items = [], isPending, refetch } = usePlaylistsQuery();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    const n = name.trim();
    if (n.length < 1) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await createPlaylist(n);
      setOpen(false);
      setName("");
      await qc.invalidateQueries({ queryKey: playlistKeys.list() });
      router.push(`/playlist/${res.data.id}` as Href);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create playlist");
    } finally {
      setBusy(false);
    }
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
          headerRight: () => (
            <Pressable
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
          contentContainerStyle={styles.list}
          onRefresh={async () => {
            await refetch();
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>No playlists yet</Text>
              <Text style={styles.emptyBody}>
                Collect videos into an ordered list, then share a public RSS
                feed.
              </Text>
              <Button label="New playlist" onPress={() => setOpen(true)} />
            </View>
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push(`/playlist/${item.id}` as Href)}
              onLongPress={() => {
                Alert.alert("Delete playlist?", item.name, [
                  { text: "Cancel", style: "cancel" },
                  {
                    text: "Delete",
                    style: "destructive",
                    onPress: () => {
                      void deletePlaylist(item.id).then(() =>
                        qc.invalidateQueries({ queryKey: playlistKeys.list() })
                      );
                    },
                  },
                ]);
              }}
              style={({ pressed }) => [
                styles.card,
                pressed && { opacity: 0.9 },
              ]}
            >
              <View style={styles.iconWrap}>
                <Ionicons name="list" size={20} color={colors.brand} />
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={styles.cardTitle}>{item.name}</Text>
                <Text style={styles.meta}>
                  {item.is_public ? "Public" : "Private"}
                </Text>
              </View>
              <Ionicons
                name="chevron-forward"
                size={18}
                color={colors.textDim}
              />
            </Pressable>
          )}
        />
      )}
      <CinemaSheet
        visible={open}
        onClose={() => setOpen(false)}
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
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button label="Create" loading={busy} onPress={() => void create()} />
      </CinemaSheet>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.lg, gap: 10, paddingBottom: 40 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderRadius: radii.md,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 16,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  empty: { paddingTop: 48, gap: 12 },
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
  sheetTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
    marginBottom: 8,
  },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
});
