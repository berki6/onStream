import { Stack, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { queryErrorText, userFacingError } from "@/api/client";
import { createLiveToken, deleteLiveStream } from "@/api/live";
import { Button } from "@/components/Button";
import { CopyRow } from "@/components/CopyRow";
import { DetailSkeleton } from "@/components/DetailSkeleton";
import { HlsPlayer } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { toast } from "@/lib/toast";
import { liveKeys } from "@/query/keys";
import { useLiveHealthQuery, useLiveStreamQuery } from "@/query/live";
import { scrollPhysics } from "@/theme/scroll";
import { colors, spacing } from "@/theme/tokens";

export default function LiveDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [focused, setFocused] = useState(true);

  const {
    data: stream,
    isPending,
    isError,
    error,
    refetch: refetchStream,
  } = useLiveStreamQuery(id, { focused });

  const {
    data: health,
    refetch: refetchHealth,
  } = useLiveHealthQuery(id, { focused });

  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      refetchStream();
      refetchHealth();
      return () => setFocused(false);
    }, [refetchStream, refetchHealth])
  );

  const ended = String(stream?.status || "").toLowerCase() === "ended";
  const cold = isPending && !stream;
  const loadError = queryErrorText(Boolean(isError && !stream), error);

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: stream?.title || "Live",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />

      {cold ? (
        <DetailSkeleton variant="live" />
      ) : loadError ? (
        <View style={styles.content}>
          <Text style={styles.error}>{loadError}</Text>
          <Button
            label="Retry"
            onPress={() => {
              void refetchStream();
              void refetchHealth();
            }}
          />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.content} {...scrollPhysics}>
          {stream ? (
            <View style={styles.meta}>
              <StatusPill status={stream.status} />
              <Text style={styles.id}>{stream.stream_id}</Text>
            </View>
          ) : null}

          {ended ? (
            <Text style={styles.endedNote}>
              Stream revoked. New playlist requests return 404. Buffered seconds
              may finish, then the player stalls. The encoder may keep
              publishing until kicked or stopped.
            </Text>
          ) : null}

          <HlsPlayer uri={ended ? null : playbackUrl} title={stream?.title} />

          {health ? (
            <View style={styles.healthBox}>
              <Text style={styles.section}>Health</Text>
              <Text style={styles.healthLine}>
                Status {health.status}
                {" · "}
                Playlist {health.playlist_present ? "present" : "missing"}
                {health.playlist_age_seconds != null
                  ? ` · age ${health.playlist_age_seconds.toFixed(1)}s`
                  : ""}
                {health.is_stale ? " · STALE" : ""}
              </Text>
            </View>
          ) : null}

          <Button
            label="Issue live playback token"
            disabled={ended}
            onPress={async () => {
              if (!id || ended) return;
              try {
                const res = await createLiveToken(id);
                setPlaybackUrl(res.data.playback_url);
              } catch (e) {
                toast.error(userFacingError(e, "Token failed"));
              }
            }}
          />
          <Button
            label="Refresh health"
            variant="ghost"
            onPress={() => {
              refetchStream();
              refetchHealth();
            }}
          />
          {!ended ? (
            <Button
              label="Revoke stream"
              variant="danger"
              loading={revoking}
              onPress={async () => {
                if (!id) return;
                setRevoking(true);
                try {
                  const res = await deleteLiveStream(id);
                  qc.setQueryData(liveKeys.detail(id), res.data);
                  await qc.invalidateQueries({ queryKey: liveKeys.list() });
                  await qc.invalidateQueries({
                    queryKey: liveKeys.health(id),
                  });
                  setPlaybackUrl(null);
                  toast.success("Stream revoked. Playback through OnStream is ended.");
                } catch (e) {
                  toast.error(userFacingError(e, "Delete failed"));
                } finally {
                  setRevoking(false);
                }
              }}
            />
          ) : (
            <Button
              label="Back to live list"
              variant="ghost"
              onPress={() => router.back()}
            />
          )}

          {playbackUrl && !ended ? (
            <CopyRow label="Playback URL" value={playbackUrl} />
          ) : null}
          {stream?.playback_url ? (
            <CopyRow label="Public playback" value={stream.playback_url} />
          ) : null}
          {stream?.webrtc_base ? (
            <CopyRow label="WebRTC base" value={stream.webrtc_base} />
          ) : null}
        </ScrollView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, gap: 14, paddingBottom: 40 },
  meta: { flexDirection: "row", alignItems: "center", gap: 12 },
  id: { color: colors.textDim, fontFamily: "DMSans_400Regular", fontSize: 13 },
  healthBox: { gap: 6 },
  section: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  healthLine: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
  },
  endedNote: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
  },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
});
