import { Stack, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError } from "@/api/client";
import {
  listModerationQueue,
  reviewModeration,
} from "@/api/moderation";
import type { Video } from "@/api/videos";
import { Button } from "@/components/Button";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { toast } from "@/lib/toast";
import { videoKeys } from "@/query/keys";
import { colors, radii, spacing } from "@/theme/tokens";

export default function ModerationScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const qc = useQueryClient();
  const [items, setItems] = useState<Video[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [makePublic, setMakePublic] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listModerationQueue();
      setItems(res.data || []);
      setTotal(res.pagination?.total_count ?? res.data?.length ?? 0);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  async function act(videoId: string, action: "approve" | "reject") {
    setBusyId(videoId);
    setError(null);
    try {
      await reviewModeration(
        videoId,
        action,
        action === "approve" ? makePublic : undefined
      );
      await load();
      await qc.invalidateQueries({ queryKey: videoKeys.list() });
      toast.success(action === "approve" ? "Approved." : "Rejected.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Review failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: "Moderation",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />
      <FormScroll
        contentContainerStyle={[
          styles.content,
          { paddingBottom: insets.bottom + 32 },
        ]}
      >
        <Text style={styles.lead}>
          Quarantined VOD assets for this account. Approve restores playback
          tokens; reject leaves them blocked.
        </Text>

        <View style={styles.toggleRow}>
          <Text style={styles.toggleLabel}>Make public on approve</Text>
          <Switch
            value={makePublic}
            onValueChange={setMakePublic}
            trackColor={{ true: colors.brand, false: colors.line }}
          />
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {loading ? (
          <ActivityIndicator color={colors.brand} />
        ) : items.length === 0 ? (
          <Text style={styles.empty}>Queue empty · {total} total</Text>
        ) : (
          items.map((v) => (
            <View key={v.upload_id} style={styles.card}>
              <Pressable
                onPress={() => router.push(`/video/${v.upload_id}`)}
              >
                <Text style={styles.title}>{v.title || v.upload_id}</Text>
                <Text style={styles.meta}>{v.upload_id}</Text>
              </Pressable>
              <View style={styles.row}>
                <StatusPill status={v.status} />
                <View style={styles.actions}>
                  <Button
                    label="Approve"
                    loading={busyId === v.upload_id}
                    style={styles.btn}
                    onPress={() => act(v.upload_id, "approve")}
                  />
                  <Button
                    label="Reject"
                    variant="danger"
                    loading={busyId === v.upload_id}
                    style={styles.btn}
                    onPress={() => act(v.upload_id, "reject")}
                  />
                </View>
              </View>
            </View>
          ))
        )}

        <Button label="Refresh" variant="ghost" onPress={load} />
      </FormScroll>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, gap: 14 },
  lead: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  toggleLabel: {
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
    flex: 1,
  },
  empty: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
  },
  card: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 14,
    gap: 10,
  },
  title: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    marginTop: 4,
  },
  row: { gap: 10 },
  actions: { flexDirection: "row", gap: 8 },
  btn: { flex: 1, minWidth: 0 },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
});
