import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import { Stack, useRouter, type Href } from "expo-router";
import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import { queryErrorText, userFacingError } from "@/api/client";
import { revokeShareLink, type ShareLink } from "@/api/shareLinks";
import { Button } from "@/components/Button";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { toast } from "@/lib/toast";
import { shareKeys, videoKeys } from "@/query/keys";
import { useShareLinksQuery } from "@/query/shares";
import { colors, radii, spacing } from "@/theme/tokens";

type Filter = "all" | "active" | "revoked";

function shareStatus(link: ShareLink): string {
  if (link.revoked_at) return "revoked";
  if (!link.active) return "expired";
  return "active";
}

function clipLabel(link: ShareLink): string | null {
  if (link.clip_start == null && link.clip_end == null) return null;
  const start = Math.round(link.clip_start ?? 0);
  if (link.clip_end == null) return `from ${start}s`;
  return `${start}–${Math.round(link.clip_end)}s`;
}

function expiryLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function ShareLinksScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: items = [], isPending, isError, error, refetch } =
    useShareLinksQuery();
  const [filter, setFilter] = useState<Filter>("all");
  const [busyId, setBusyId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (filter === "active") return items.filter((l) => l.active);
    if (filter === "revoked") return items.filter((l) => Boolean(l.revoked_at));
    return items;
  }, [items, filter]);

  const listError = queryErrorText(isError, error, items.length > 0);

  const revoke = async (link: ShareLink) => {
    setBusyId(link.public_id);
    try {
      await revokeShareLink(link.public_id);
      await qc.invalidateQueries({ queryKey: shareKeys.list() });
      await qc.invalidateQueries({ queryKey: videoKeys.shares(link.video_id) });
      toast.success("Share link revoked.");
    } catch (e) {
      toast.error(userFacingError(e, "Revoke failed"));
    } finally {
      setBusyId(null);
    }
  };

  const copyId = async (publicId: string) => {
    await Clipboard.setStringAsync(publicId);
    toast.success("Copied public id. Watch URLs cannot be rebuilt from this list.");
  };

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: "Share links",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
          headerShadowVisible: false,
        }}
      />
      {isPending && items.length === 0 ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ElasticRefreshFlatList
          data={filtered}
          keyExtractor={(item) => item.public_id}
          contentContainerStyle={[
            styles.list,
            filtered.length === 0 && styles.listEmpty,
          ]}
          onRefresh={async () => {
            await refetch();
          }}
          ListHeaderComponent={
            <View style={styles.headerBlock}>
              <Text style={styles.lead}>
                Tokens are shown once at create. This inbox is for audit and
                revoke — copy a public id, not a watch URL.
              </Text>
              {listError ? <Text style={styles.error}>{listError}</Text> : null}
              <View style={styles.filters}>
                {(
                  [
                    ["all", "All"],
                    ["active", "Active"],
                    ["revoked", "Revoked"],
                  ] as const
                ).map(([id, label]) => {
                  const on = filter === id;
                  return (
                    <Pressable
                      key={id}
                      accessibilityRole="button"
                      accessibilityState={{ selected: on }}
                      onPress={() => setFilter(id)}
                      style={[styles.chip, on && styles.chipOn]}
                    >
                      <Text style={[styles.chipText, on && styles.chipTextOn]}>
                        {label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              {items.length > 0 ? (
                <Text style={styles.count}>
                  {filtered.length} of {items.length}
                </Text>
              ) : null}
            </View>
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Ionicons name="link-outline" size={32} color={colors.brand} />
              </View>
              <Text style={styles.emptyKicker}>Share</Text>
              <Text style={styles.emptyTitle}>
                {items.length === 0
                  ? "No share links yet"
                  : "Nothing in this filter"}
              </Text>
              <Text style={styles.emptyBody}>
                {items.length === 0
                  ? "Create a link from a READY video’s share sheet. The token is copied once; come back here to revoke."
                  : "Switch to All to see expired or other statuses."}
              </Text>
              {items.length === 0 ? (
                <Pressable
                  onPress={() => router.push("/(tabs)/videos" as Href)}
                  style={({ pressed }) => [
                    styles.emptyCta,
                    pressed && { opacity: 0.9, transform: [{ scale: 0.98 }] },
                  ]}
                >
                  <Ionicons name="film-outline" size={18} color={colors.bg} />
                  <Text style={styles.emptyCtaText}>Open library</Text>
                </Pressable>
              ) : null}
            </View>
          }
          renderItem={({ item }) => {
            const status = shareStatus(item);
            const clip = clipLabel(item);
            const views =
              item.max_views != null
                ? `${item.view_count}/${item.max_views} views`
                : `${item.view_count} view${item.view_count === 1 ? "" : "s"}`;
            return (
              <View style={styles.card}>
                <Pressable
                  onPress={() => router.push(`/video/${item.video_id}` as Href)}
                  style={({ pressed }) => pressed && { opacity: 0.85 }}
                >
                  <Text style={styles.cardTitle} numberOfLines={2}>
                    {item.video_title || item.label || item.video_id}
                  </Text>
                  {item.label && item.video_title ? (
                    <Text style={styles.label} numberOfLines={1}>
                      {item.label}
                    </Text>
                  ) : null}
                  <Text style={styles.meta}>
                    {item.public_id}
                    {clip ? ` · clip ${clip}` : ""}
                  </Text>
                  <Text style={styles.meta}>
                    {views} · expires {expiryLabel(item.expires_at)}
                  </Text>
                </Pressable>
                <View style={styles.row}>
                  <StatusPill status={status} />
                  <View style={styles.actions}>
                    <Button
                      label="Copy id"
                      variant="ghost"
                      style={styles.btn}
                      onPress={() => void copyId(item.public_id)}
                    />
                    <Button
                      label="Open"
                      variant="ghost"
                      style={styles.btn}
                      onPress={() =>
                        router.push(`/video/${item.video_id}` as Href)
                      }
                    />
                    {item.active ? (
                      <Button
                        label="Revoke"
                        variant="danger"
                        loading={busyId === item.public_id}
                        style={styles.btn}
                        onPress={() => void revoke(item)}
                      />
                    ) : null}
                  </View>
                </View>
              </View>
            );
          }}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.lg, gap: 10, paddingBottom: 40 },
  listEmpty: { flexGrow: 1 },
  headerBlock: { gap: 12, marginBottom: 4 },
  lead: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  filters: { flexDirection: "row", gap: 8 },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radii.xl,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  chipOn: {
    borderColor: "rgba(46, 230, 166, 0.45)",
    backgroundColor: colors.brandSoft,
  },
  chipText: {
    color: colors.textMuted,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
    letterSpacing: 0.4,
  },
  chipTextOn: { color: colors.brand },
  count: {
    color: colors.textDim,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  card: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 14,
    gap: 10,
  },
  cardTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  label: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
    marginTop: 4,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    marginTop: 4,
  },
  row: { gap: 10 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  btn: { flexGrow: 1, minWidth: 88 },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  empty: {
    alignItems: "center",
    gap: 10,
    paddingHorizontal: spacing.xl,
    paddingTop: 24,
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
});
