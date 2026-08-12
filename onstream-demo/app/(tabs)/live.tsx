import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { type LiveStream } from "@/api/live";
import { Button } from "@/components/Button";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { prefetchLive, useLiveListQuery } from "@/query/live";
import { colors, radii, spacing } from "@/theme/tokens";

type Row =
  | { kind: "header"; id: string; title: string; subtitle?: string }
  | { kind: "stream"; id: string; stream: LiveStream };

function isEnded(s: LiveStream) {
  return String(s.status || "").toLowerCase() === "ended";
}

export default function LiveTabScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const qc = useQueryClient();

  const {
    data: items = [],
    isPending,
    isError,
    error,
    refetch,
  } = useLiveListQuery();

  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch])
  );

  const rows: Row[] = useMemo(() => {
    const active = items.filter((s) => !isEnded(s));
    const ended = items.filter(isEnded).slice(0, 8);
    const out: Row[] = [];
    out.push({
      kind: "header",
      id: "hdr-active",
      title: "Active",
      subtitle: active.length
        ? undefined
        : "Nothing live or idle right now. Create a stream, or check Recently ended after revoke.",
    });
    for (const s of active) {
      out.push({ kind: "stream", id: s.stream_id, stream: s });
    }
    if (ended.length) {
      out.push({
        kind: "header",
        id: "hdr-ended",
        title: "Recently ended",
        subtitle:
          "Revoked streams stay openable for health/history; they are not playable.",
      });
      for (const s of ended) {
        out.push({ kind: "stream", id: `ended-${s.stream_id}`, stream: s });
      }
    }
    return out;
  }, [items]);

  const listError = isError
    ? error instanceof Error
      ? error.message
      : "Failed to load live streams"
    : null;

  return (
    <Screen>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Broadcast</Text>
          <Text style={styles.title}>Live</Text>
        </View>
        <Button
          label="Create"
          style={{ minWidth: 100 }}
          onPress={() => router.push("/live/create")}
        />
      </View>

      {listError ? <Text style={styles.error}>{listError}</Text> : null}

      {isPending && items.length === 0 ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ElasticRefreshFlatList
          data={rows}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          onRefresh={async () => {
            await refetch();
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="radio-outline" size={40} color={colors.textDim} />
              <Text style={styles.emptyTitle}>No streams yet</Text>
              <Text style={styles.emptyBody}>
                Create one to grab RTMP / WHIP URLs, publish with OBS or the lab
                FFmpeg script, then play HLS here. After revoke, ended streams
                appear under Recently ended.
              </Text>
            </View>
          }
          renderItem={({ item }) => {
            if (item.kind === "header") {
              return (
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>{item.title}</Text>
                  {item.subtitle ? (
                    <Text style={styles.sectionBody}>{item.subtitle}</Text>
                  ) : null}
                </View>
              );
            }
            const stream = item.stream;
            const ended = isEnded(stream);
            const st = String(stream.status || "").toLowerCase();
            return (
              <Pressable
                onPressIn={() => {
                  prefetchLive(qc, stream.stream_id);
                }}
                onPress={() => router.push(`/live/${stream.stream_id}`)}
                style={[styles.card, ended && styles.cardEnded]}
              >
                <View style={styles.cardTop}>
                  <Ionicons
                    name={
                      st === "live"
                        ? "radio"
                        : st === "idle"
                          ? "pause-circle-outline"
                          : "stop-circle-outline"
                    }
                    size={20}
                    color={
                      st === "live"
                        ? colors.live
                        : st === "idle"
                          ? colors.warning
                          : colors.textDim
                    }
                  />
                  <Text style={styles.cardTitle} numberOfLines={1}>
                    {stream.title}
                  </Text>
                  <StatusPill status={stream.status} />
                </View>
                <Text style={styles.meta}>{stream.stream_id}</Text>
                {ended ? (
                  <Text style={styles.endedHint}>
                    Playback returns 404 — open for status / notes
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
    color: colors.text,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 34,
    letterSpacing: -0.8,
  },
  list: { paddingHorizontal: spacing.lg, paddingBottom: 40, gap: 12 },
  section: { gap: 4, paddingTop: 8 },
  sectionTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  sectionBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
    lineHeight: 18,
  },
  card: {
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 16,
    gap: 8,
  },
  cardEnded: {
    opacity: 0.85,
    borderColor: colors.textDim,
  },
  cardTop: { flexDirection: "row", alignItems: "center", gap: 10 },
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
  endedHint: {
    color: colors.textMuted,
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
